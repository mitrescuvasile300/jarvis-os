"""Core Jarvis Agent — the brain of the system.

Implements the perceive → think → act loop:
1. Perceive: Receive input (message, event, cron trigger)
2. Think: Consult LLM with context (memory, tools, skills)
3. Act: Execute tools, update memory, respond
"""

import logging
from datetime import datetime
from typing import Any

from jarvis.llm import create_llm_client
from jarvis.memory_store import MemoryStore
from jarvis.tools import ToolRegistry
from jarvis.skill_loader import SkillLoader

logger = logging.getLogger("jarvis.agent")


class JarvisAgent:
    def __init__(self, config: dict):
        self.config = config
        self.name = config["agent"]["name"]
        self.started_at = datetime.now()

        # Components (initialized in .initialize())
        self.llm = None
        self.memory = None
        self.tools = ToolRegistry()
        self.skills: dict = {}
        self.integrations: dict = {}

    async def initialize(self):
        """Initialize all components. Call once before use."""
        logger.info(f"Initializing {self.name}...")

        # 1. LLM client
        llm_config = self.config["agent"]["llm"]
        self.llm = create_llm_client(llm_config)
        logger.info(f"LLM: {llm_config['provider']} / {llm_config['model']}")

        # 2. Memory
        self.memory = MemoryStore(self.config["memory"])
        await self.memory.initialize()
        count = await self.memory.count()
        logger.info(f"Memory initialized: {count} entries")

        # 3. Tools
        self.tools.register_defaults()
        logger.info(f"Tools registered: {', '.join(self.tools.list())}")

        # 4. Skills
        skill_loader = SkillLoader(self.config.get("skills", {}), self.tools, self.llm, self.memory)
        self.skills = await skill_loader.load_all()
        logger.info(f"Skills loaded: {', '.join(self.skills.keys()) or 'none'}")

        # 5. Integrations
        self.integrations = self._init_integrations()
        logger.info(f"Integrations: {', '.join(self.integrations.keys()) or 'none'}")

        logger.info(f"{self.name} is ready!")

    def _init_integrations(self) -> dict:
        """Initialize configured integrations."""
        integrations = {}
        int_config = self.config.get("integrations", {})

        if int_config.get("slack", {}).get("bot_token"):
            integrations["slack"] = {"status": "configured"}
            logger.info("Slack integration configured")

        if int_config.get("twitter", {}).get("api_key"):
            integrations["twitter"] = {"status": "configured"}
            logger.info("Twitter integration configured")

        if int_config.get("github", {}).get("token"):
            integrations["github"] = {"status": "configured"}
            logger.info("GitHub integration configured")

        return integrations

    async def chat(self, message: str, conversation_id: str = "default") -> dict:
        """Process a chat message through the full agent loop.

        Returns:
            dict with keys: text, tools_used, memory_updated
        """
        logger.info(f"[{conversation_id}] User: {message[:100]}...")

        # 1. PERCEIVE — gather context
        # Retrieve relevant memories
        relevant_memories = await self.memory.search(message, limit=5)
        # Get conversation history
        conversation = await self.memory.get_conversation(conversation_id, limit=20)

        # 2. THINK — build prompt and call LLM
        system_prompt = self._build_system_prompt()
        messages = self._build_messages(system_prompt, conversation, relevant_memories, message)

        # Available tools for the LLM
        tool_definitions = self.tools.get_definitions()

        # Call LLM with tool use
        response = await self.llm.chat(
            messages=messages,
            tools=tool_definitions,
            temperature=self.config["agent"]["llm"].get("temperature", 0.7),
            max_tokens=self.config["agent"]["llm"].get("max_tokens", 4096),
        )

        # 3. ACT — execute tools if requested
        tools_used = []
        if response.get("tool_calls"):
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                logger.info(f"Executing tool: {tool_name}({tool_args})")
                try:
                    result = await self.tools.execute(tool_name, tool_args)
                    tools_used.append({"name": tool_name, "result": str(result)[:500]})
                except Exception as e:
                    logger.error(f"Tool {tool_name} failed: {e}")
                    tools_used.append({"name": tool_name, "error": str(e)})

            # If tools were used, get a follow-up response
            if tools_used:
                messages.append({"role": "assistant", "content": response.get("text", "")})
                messages.append({
                    "role": "system",
                    "content": f"Tool results:\n{self._format_tool_results(tools_used)}",
                })
                response = await self.llm.chat(
                    messages=messages,
                    temperature=self.config["agent"]["llm"].get("temperature", 0.7),
                    max_tokens=self.config["agent"]["llm"].get("max_tokens", 4096),
                )

        # 4. REMEMBER — store conversation and extract knowledge
        response_text = response.get("text", "I couldn't generate a response.")
        await self.memory.store_message(conversation_id, "user", message)
        await self.memory.store_message(conversation_id, "assistant", response_text)

        # Extract and store any important facts
        memory_updated = await self._extract_and_store_knowledge(message, response_text)

        logger.info(f"[{conversation_id}] {self.name}: {response_text[:100]}...")

        return {
            "text": response_text,
            "tools_used": [t["name"] for t in tools_used],
            "memory_updated": memory_updated,
        }

    async def run_skill(self, skill_name: str, action: str, params: dict) -> Any:
        """Execute a skill action."""
        if skill_name not in self.skills:
            raise KeyError(f"Skill '{skill_name}' not found")

        skill = self.skills[skill_name]
        return await skill.execute(action, params)

    def _build_system_prompt(self) -> str:
        """Build the full system prompt from components."""
        prompt_parts = []

        # Load base system prompt
        try:
            with open("agent/prompts/system.md") as f:
                prompt_parts.append(f.read())
        except FileNotFoundError:
            prompt_parts.append(f"You are {self.name}, a helpful AI assistant.")

        # Load personality
        try:
            import yaml
            with open("agent/prompts/personality.yml") as f:
                personality = yaml.safe_load(f)
            if personality:
                traits = personality.get("traits", [])
                style = personality.get("communication_style", "")
                if traits:
                    prompt_parts.append(f"\nYour personality traits: {', '.join(traits)}")
                if style:
                    prompt_parts.append(f"\nCommunication style: {style}")
        except FileNotFoundError:
            pass

        # Load rules
        try:
            import yaml
            with open("agent/prompts/rules.yml") as f:
                rules = yaml.safe_load(f)
            if rules and rules.get("rules"):
                prompt_parts.append("\nRules you must follow:")
                for rule in rules["rules"]:
                    prompt_parts.append(f"- {rule}")
        except FileNotFoundError:
            pass

        # Add available skills info
        if self.skills:
            prompt_parts.append("\nYou have these skills available:")
            for name, skill in self.skills.items():
                prompt_parts.append(f"- {name}: {skill.description}")

        return "\n".join(prompt_parts)

    def _build_messages(
        self,
        system_prompt: str,
        conversation: list[dict],
        memories: list[dict],
        current_message: str,
    ) -> list[dict]:
        """Build the full message list for the LLM."""
        messages = [{"role": "system", "content": system_prompt}]

        # Add relevant memories as context
        if memories:
            memory_text = "\n".join(
                f"[Memory] {m['content']}" for m in memories if m.get("content")
            )
            messages.append({
                "role": "system",
                "content": f"Relevant memories:\n{memory_text}",
            })

        # Add conversation history
        for msg in conversation:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current message
        messages.append({"role": "user", "content": current_message})

        return messages

    def _format_tool_results(self, tools_used: list[dict]) -> str:
        """Format tool results for the LLM."""
        parts = []
        for tool in tools_used:
            if "error" in tool:
                parts.append(f"❌ {tool['name']}: Error — {tool['error']}")
            else:
                parts.append(f"✅ {tool['name']}: {tool['result']}")
        return "\n".join(parts)

    async def _extract_and_store_knowledge(self, user_msg: str, assistant_msg: str) -> bool:
        """Ask the LLM to extract any important facts to remember."""
        try:
            extraction = await self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract key facts, preferences, or decisions from this conversation "
                            "that should be remembered long-term. Return a JSON array of strings, "
                            "or an empty array [] if nothing important to remember. "
                            "Only extract genuinely important information."
                        ),
                    },
                    {"role": "user", "content": f"User: {user_msg}\nAssistant: {assistant_msg}"},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            import json
            text = extraction.get("text", "[]")
            # Try to parse JSON from the response
            try:
                facts = json.loads(text)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                if "```" in text:
                    text = text.split("```")[1].strip()
                    if text.startswith("json"):
                        text = text[4:].strip()
                    facts = json.loads(text)
                else:
                    facts = []

            if facts and isinstance(facts, list):
                for fact in facts:
                    await self.memory.store_knowledge(str(fact))
                logger.info(f"Stored {len(facts)} new knowledge entries")
                return True

        except Exception as e:
            logger.debug(f"Knowledge extraction skipped: {e}")

        return False

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info(f"Shutting down {self.name}...")
        if self.memory:
            await self.memory.close()
        logger.info("Shutdown complete")

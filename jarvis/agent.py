"""Core Jarvis Agent — the brain of the system.

Implements the disciplined memory loop:
1. RECALL  — read knowledge files + search memory for context
2. THINK   — build rich prompt with all context, call LLM
3. ACT     — execute tools, handle multi-step reasoning
4. LEARN   — extract knowledge, update files on disk
5. RESPOND — deliver the answer

The key insight: memory works because of DISCIPLINE (always read before,
always update after), not because of fancy databases.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any

from jarvis.llm import create_llm_client
from jarvis.memory_store import MemoryStore
from jarvis.tools import ToolRegistry
from jarvis.skill_loader import SkillLoader
from jarvis.knowledge_manager import KnowledgeManager

logger = logging.getLogger("jarvis.agent")

# Messages shorter than this skip knowledge extraction (trivial messages)
TRIVIAL_MESSAGE_THRESHOLD = 15
TRIVIAL_PATTERNS = {"hi", "hello", "hey", "ok", "yes", "no", "thanks",
                     "da", "nu", "ok", "salut", "mersi", "bine"}


class JarvisAgent:
    def __init__(self, config: dict):
        self.config = config
        self.name = config["agent"]["name"]
        self.started_at = datetime.now()

        # Components (initialized in .initialize())
        self.llm = None
        self.memory = None
        self.knowledge = None
        self.tools = ToolRegistry()
        self.skills: dict = {}
        self.integrations: dict = {}

        # Conversation tracking for smart summarization
        self._turn_counts: dict[str, int] = {}

    async def initialize(self):
        """Initialize all components. Call once before use."""
        logger.info(f"Initializing {self.name}...")

        # 1. LLM client
        llm_config = self.config["agent"]["llm"]
        self.llm = create_llm_client(llm_config)
        logger.info(f"LLM: {llm_config['provider']} / {llm_config['model']}")

        # 2. Memory (database)
        self.memory = MemoryStore(self.config["memory"])
        await self.memory.initialize()
        count = await self.memory.count()
        logger.info(f"Memory initialized: {count} entries")

        # 3. Knowledge (disk-based files — the discipline system)
        knowledge_config = self.config.get("knowledge", {})
        self.knowledge = KnowledgeManager(
            config=knowledge_config,
            knowledge_dir=knowledge_config.get("directory", "knowledge"),
        )
        await self.knowledge.initialize()

        # 4. Tools
        self.tools.register_defaults()
        logger.info(f"Tools registered: {', '.join(self.tools.list())}")

        # 5. Skills
        skill_loader = SkillLoader(
            self.config.get("skills", {}), self.tools, self.llm, self.memory
        )
        self.skills = await skill_loader.load_all()
        logger.info(f"Skills loaded: {', '.join(self.skills.keys()) or 'none'}")

        # 6. Integrations
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
        """Process a chat message through the disciplined agent loop.

        Returns:
            dict with keys: text, tools_used, memory_updated, knowledge_recalled
        """
        logger.info(f"[{conversation_id}] User: {message[:100]}...")

        # ─── 1. RECALL — Read before acting ────────────────
        # Search memory database for relevant past conversations
        relevant_memories = await self.memory.search(message, limit=5)

        # Read knowledge files from disk (the discipline!)
        knowledge_context = await self.knowledge.recall(message)

        # Get conversation history (with smart summarization)
        conversation = await self._get_smart_conversation(conversation_id)

        logger.debug(
            f"[{conversation_id}] Recalled: {len(relevant_memories)} memories, "
            f"{len(knowledge_context)} knowledge files, "
            f"{len(conversation)} conversation messages"
        )

        # ─── 2. THINK — Build rich prompt, call LLM ───────
        system_prompt = self._build_system_prompt(knowledge_context)
        messages = self._build_messages(
            system_prompt, conversation, relevant_memories, message
        )

        # Available tools for the LLM
        tool_definitions = self.tools.get_definitions()

        # Call LLM
        response = await self.llm.chat(
            messages=messages,
            tools=tool_definitions,
            temperature=self.config["agent"]["llm"].get("temperature", 0.7),
            max_tokens=self.config["agent"]["llm"].get("max_tokens", 4096),
        )

        # ─── 3. ACT — Execute tools (multi-step) ──────────
        tools_used = []
        max_tool_rounds = self.config["agent"].get("max_tool_rounds", 3)
        round_num = 0

        while response.get("tool_calls") and round_num < max_tool_rounds:
            round_num += 1
            round_results = []

            for tool_call in response["tool_calls"]:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                logger.info(f"[Round {round_num}] Executing tool: {tool_name}")

                try:
                    result = await self.tools.execute(tool_name, tool_args)
                    round_results.append({
                        "name": tool_name,
                        "result": str(result)[:1000],
                    })
                    tools_used.append(tool_name)
                except Exception as e:
                    logger.error(f"Tool {tool_name} failed: {e}")
                    round_results.append({
                        "name": tool_name,
                        "error": str(e),
                    })
                    tools_used.append(f"{tool_name}(failed)")

            # Give results back to LLM for next step
            messages.append({
                "role": "assistant",
                "content": response.get("text", ""),
            })
            messages.append({
                "role": "system",
                "content": f"Tool results (round {round_num}):\n"
                           f"{self._format_tool_results(round_results)}",
            })

            response = await self.llm.chat(
                messages=messages,
                tools=tool_definitions,
                temperature=self.config["agent"]["llm"].get("temperature", 0.7),
                max_tokens=self.config["agent"]["llm"].get("max_tokens", 4096),
            )

        # ─── 4. REMEMBER — Store conversation ─────────────
        response_text = response.get("text", "I couldn't generate a response.")
        await self.memory.store_message(conversation_id, "user", message)
        await self.memory.store_message(conversation_id, "assistant", response_text)

        # Track turn count for summarization
        self._turn_counts[conversation_id] = self._turn_counts.get(conversation_id, 0) + 1

        # ─── 5. LEARN — Update knowledge files ────────────
        # (the discipline! — always update after acting)
        memory_updated = False
        if not self._is_trivial(message):
            await self.knowledge.learn(self.llm, message, response_text, tools_used)
            memory_updated = True

        # Summarize old conversation if getting long
        if self._turn_counts[conversation_id] % 15 == 0:
            await self._maybe_summarize_conversation(conversation_id)

        logger.info(f"[{conversation_id}] {self.name}: {response_text[:100]}...")

        return {
            "text": response_text,
            "tools_used": [t for t in tools_used if not t.endswith("(failed)")],
            "memory_updated": memory_updated,
            "knowledge_recalled": list(knowledge_context.keys()),
        }

    # ── Smart Conversation Management ────────────────────────

    async def _get_smart_conversation(self, conversation_id: str) -> list[dict]:
        """Get conversation with smart context management.

        Instead of sending all 50 messages, we:
        1. Include the summary of older messages (if available)
        2. Include the last N recent messages in full
        """
        recent_limit = self.config["agent"].get("recent_messages", 20)
        conversation = await self.memory.get_conversation(
            conversation_id, limit=recent_limit
        )

        # Check if there's a summary for older context
        summary = await self.memory.get_working(
            f"conversation_summary:{conversation_id}"
        )

        if summary:
            # Prepend summary as context
            summary_msg = {
                "role": "system",
                "content": f"[Summary of earlier conversation]\n{summary}",
            }
            conversation = [summary_msg] + conversation

        return conversation

    async def _maybe_summarize_conversation(self, conversation_id: str):
        """Summarize older conversation messages to save context window."""
        try:
            all_messages = await self.memory.get_conversation(
                conversation_id, limit=50
            )

            if len(all_messages) < 20:
                return

            # Summarize the older half
            older = all_messages[:-10]
            older_text = "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in older
            )

            result = await self.llm.chat(
                messages=[
                    {"role": "system", "content": (
                        "Summarize this conversation in 3-5 bullet points. "
                        "Focus on: key topics discussed, decisions made, "
                        "user preferences expressed, and any pending items. "
                        "Write in the same language as the conversation."
                    )},
                    {"role": "user", "content": older_text[:4000]},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            summary = result.get("text", "")
            if summary:
                await self.memory.set_working(
                    f"conversation_summary:{conversation_id}",
                    summary,
                    task_id=conversation_id,
                )
                logger.info(
                    f"Summarized conversation {conversation_id}: "
                    f"{len(older)} messages → {len(summary)} chars"
                )

        except Exception as e:
            logger.debug(f"Summarization skipped: {e}")

    def _is_trivial(self, message: str) -> bool:
        """Check if a message is too trivial for knowledge extraction."""
        clean = message.strip().lower().rstrip("!?.,")
        if len(clean) < TRIVIAL_MESSAGE_THRESHOLD:
            return True
        if clean in TRIVIAL_PATTERNS:
            return True
        return False

    # ── Skill Execution ──────────────────────────────────────

    async def run_skill(self, skill_name: str, action: str, params: dict) -> Any:
        """Execute a skill action."""
        if skill_name not in self.skills:
            raise KeyError(f"Skill '{skill_name}' not found")

        skill = self.skills[skill_name]
        return await skill.execute(action, params)

    # ── Prompt Building ──────────────────────────────────────

    def _build_system_prompt(self, knowledge_context: dict[str, str] = None) -> str:
        """Build the full system prompt with knowledge context."""
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
                    prompt_parts.append(
                        f"\nYour personality traits: {', '.join(traits)}"
                    )
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

        # Inject knowledge context (the discipline!)
        if knowledge_context and self.knowledge:
            knowledge_str = self.knowledge.format_for_prompt(knowledge_context)
            if knowledge_str:
                prompt_parts.append(f"\n{knowledge_str}")

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

        # Add relevant memories (from database search)
        if memories:
            # Deduplicate and rank memories
            seen = set()
            unique_memories = []
            for m in memories:
                content = m.get("content", "")
                content_hash = hashlib.md5(content.encode()).hexdigest()
                if content_hash not in seen and content:
                    seen.add(content_hash)
                    unique_memories.append(m)

            if unique_memories:
                memory_text = "\n".join(
                    f"- {m['content']}" for m in unique_memories[:5]
                )
                messages.append({
                    "role": "system",
                    "content": f"Relevant past interactions:\n{memory_text}",
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

    # ── Knowledge Consolidation ──────────────────────────────

    async def consolidate_knowledge(self):
        """Run knowledge consolidation (call periodically)."""
        if self.knowledge:
            await self.knowledge.consolidate(self.llm)

    async def get_knowledge_stats(self) -> dict:
        """Get knowledge system statistics."""
        stats = {}
        if self.knowledge:
            stats["knowledge"] = await self.knowledge.get_stats()
        if self.memory:
            stats["memory_entries"] = await self.memory.count()
        return stats

    # ── Lifecycle ────────────────────────────────────────────

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info(f"Shutting down {self.name}...")
        if self.memory:
            await self.memory.close()
        logger.info("Shutdown complete")

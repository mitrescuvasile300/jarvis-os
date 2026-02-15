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
import re
from datetime import datetime
from typing import Any

from jarvis.llm import create_llm_client
from jarvis.memory_store import MemoryStore
from jarvis.tools import ToolRegistry
from jarvis.skill_loader import SkillLoader
from jarvis.knowledge_manager import KnowledgeManager
from jarvis.onboarding import OnboardingManager

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
        self.onboarding = None
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

        # 3b. Onboarding manager
        self.onboarding = OnboardingManager(self.knowledge)

        # 4. Tools
        self.tools.register_defaults()

        # Browser tools (Playwright)
        try:
            from jarvis.browser_tool import register_browser_tools
            register_browser_tools(self.tools)
        except ImportError:
            logger.warning("Playwright not installed — browser tools disabled")

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

    async def chat(self, message: str, conversation_id: str = "default", images: list[str] | None = None) -> dict:
        """Process a chat message through the disciplined agent loop.

        Args:
            message: The user's text message.
            conversation_id: Conversation thread identifier.
            images: Optional list of image file paths to include (vision).

        Returns:
            dict with keys: text, tools_used, memory_updated, knowledge_recalled
        """
        img_info = f", {len(images)} images" if images else ""
        logger.info(f"[{conversation_id}] User: {message[:100]}...{img_info}")

        # ─── 0. ONBOARDING CHECK ──────────────────────────
        # If Jarvis doesn't know the user yet, start the onboarding flow
        onboarding_response = await self._handle_onboarding(message, conversation_id)
        if onboarding_response:
            return onboarding_response

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
            system_prompt, conversation, relevant_memories, message, images=images
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
        logger.info(
            f"[{conversation_id}] LLM response: "
            f"text={len(response.get('text', ''))} chars, "
            f"tool_calls={len(response.get('tool_calls', []))} calls"
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
                tool_call_id = tool_call.get("id", f"call_{round_num}_{tool_name}")
                logger.info(f"[Round {round_num}] Executing tool: {tool_name}({tool_args})")

                try:
                    result = await self.tools.execute(tool_name, tool_args)
                    round_results.append({
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "result": str(result)[:2000],
                    })
                    tools_used.append(tool_name)
                except Exception as e:
                    logger.error(f"Tool {tool_name} failed: {e}")
                    round_results.append({
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "result": f"Error: {e}",
                    })
                    tools_used.append(f"{tool_name}(failed)")

            # Feed tool results back to LLM using correct OpenAI format:
            # 1. Assistant message with tool_calls attached
            # 2. One "tool" role message per result with matching tool_call_id
            assistant_msg = {"role": "assistant", "content": response.get("text") or ""}
            if response.get("raw_tool_calls"):
                assistant_msg["tool_calls"] = response["raw_tool_calls"]
            messages.append(assistant_msg)

            for tr in round_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": tr["result"],
                })

            try:
                response = await self.llm.chat(
                    messages=messages,
                    tools=tool_definitions,
                    temperature=self.config["agent"]["llm"].get("temperature", 0.7),
                    max_tokens=self.config["agent"]["llm"].get("max_tokens", 4096),
                )
                logger.info(
                    f"[{conversation_id}] Tool follow-up LLM: "
                    f"text={len(response.get('text', ''))} chars"
                )
            except Exception as e:
                logger.error(f"[{conversation_id}] LLM follow-up failed: {e}")
                # Fall back to summarizing tool results
                tool_summary = "\n".join(
                    f"- {tr['name']}: {tr['result'][:200]}" for tr in round_results
                )
                response = {"text": f"I used these tools:\n{tool_summary}"}
                break

        # ─── 4. REMEMBER — Store conversation ─────────────
        response_text = response.get("text") or "I processed your request but couldn't generate a text response."
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

    # ── Skill Knowledge Injection ─────────────────────────────

    def _inject_skill_knowledge(self, prompt_parts: list[str]):
        """Inject SKILL.md knowledge from community skills into the prompt.

        This gives Jarvis knowledge about available tools and integrations
        (Google Workspace, Brave Search, Whisper, etc.) without requiring
        the full SKILL.md to be loaded every time. Instead, we inject a
        compact reference that the agent can use to answer questions and
        use these tools.
        """
        from pathlib import Path

        community_dir = Path("skills-community")
        if not community_dir.exists():
            return

        # Build compact skill reference
        skill_refs = []
        for skill_dir in sorted(community_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # Check if this skill is enabled
            if self.config.get("skills", {}).get("enabled"):
                if skill_dir.name not in self.config["skills"]["enabled"]:
                    continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                # Strip frontmatter
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end > 0:
                        content = content[end+3:].strip()

                # Truncate very large skills to essentials (first 1500 chars)
                if len(content) > 1500:
                    content = content[:1500] + "\n[... truncated, read full SKILL.md for details]"

                skill_refs.append(f"\n### {skill_dir.name}\n{content}")
            except Exception:
                continue

        if skill_refs:
            prompt_parts.append(
                "\n\n## Installed Skills Reference\n"
                "You have these tools and integrations installed. "
                "Use them when relevant to help the user.\n"
                + "\n".join(skill_refs)
            )

    # ── Onboarding Flow ───────────────────────────────────────

    async def _handle_onboarding(self, message: str, conversation_id: str) -> dict | None:
        """Handle onboarding flow if active. Returns response dict or None."""
        if not self.onboarding:
            return None

        # Check if there's an active onboarding session
        onboarding_state = await self.memory.get_working("onboarding_state")

        # If no active session, check if onboarding is needed
        if not onboarding_state:
            if self.onboarding.needs_onboarding():
                # Start onboarding!
                state = self.onboarding.get_onboarding_state()
                await self.memory.set_working("onboarding_state", state)
                intro = self.onboarding.get_intro_message()
                logger.info("Starting onboarding flow for new user")
                return {
                    "text": intro,
                    "tools_used": [],
                    "memory_updated": False,
                    "knowledge_recalled": [],
                    "onboarding": True,
                }
            return None  # No onboarding needed

        # Active onboarding — process through LLM for natural conversation
        if not onboarding_state.get("active"):
            return None

        from jarvis.onboarding import ONBOARDING_QUESTIONS

        state = onboarding_state
        current_idx = state["current_question_idx"]
        current_q = ONBOARDING_QUESTIONS[current_idx] if current_idx < len(ONBOARDING_QUESTIONS) else None

        # Build conversation context for LLM
        answered_summary = ""
        if state["answers"]:
            lines = []
            for qid, data in state["answers"].items():
                lines.append(f"- {data['knowledge_key']}: {data['answer']}")
            answered_summary = "What I already know about the user:\n" + "\n".join(lines)

        remaining_qs = []
        for i in range(current_idx, min(current_idx + 3, len(ONBOARDING_QUESTIONS))):
            remaining_qs.append(f"  {i+1}. {ONBOARDING_QUESTIONS[i]['question']}")

        try:
            llm_response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": (
                        f"You are Jarvis, an AI personal assistant. You're getting to know a new user "
                        f"through a casual onboarding conversation.\n\n"
                        f"IMPORTANT RULES:\n"
                        f"- You are having a REAL conversation, not running a questionnaire\n"
                        f"- If the user asks you something, ANSWER their question naturally first\n"
                        f"- If the user gives feedback or complaints, ACKNOWLEDGE and RESPOND to them\n"
                        f"- Only ask the next onboarding question when it flows naturally\n"
                        f"- Match the user's language (if they write in Romanian, reply in Romanian)\n"
                        f"- Be warm, genuine, and show personality — NOT robotic\n"
                        f"- NEVER just say 'Înțeleg' or 'Got it' and move on — actually engage\n"
                        f"- If the user's message contains useful info about them, extract it even if\n"
                        f"  it wasn't a direct answer to the current question\n\n"
                        f"{answered_summary}\n\n"
                        f"Current onboarding question ({current_idx+1}/{len(ONBOARDING_QUESTIONS)}): "
                        f"{current_q['question'] if current_q else 'ALL DONE'}\n\n"
                        f"Upcoming questions:\n" + "\n".join(remaining_qs) + "\n\n"
                        f"At the END of your response, output a JSON block with what you learned:\n"
                        f"```json\n"
                        f'{{"answered_current": true/false, "extracted_info": {{"key": "value"}}, "advance": true/false}}\n'
                        f"```\n"
                        f"- answered_current: did the user answer the current question?\n"
                        f"- extracted_info: any useful info you learned (use knowledge_key names)\n"
                        f"- advance: should we move to the next question?\n"
                    )},
                    {"role": "user", "content": message},
                ],
                temperature=0.8,
                max_tokens=500,
            )
            response_text = llm_response.get("text", "")
        except Exception as e:
            logger.error(f"Onboarding LLM error: {e}")
            # Fallback: simple acknowledge + next question
            state["current_question_idx"] = current_idx + 1
            await self.memory.set_working("onboarding_state", state)
            next_q = current_q["question"] if current_q else "What can I help you with?"
            return {
                "text": f"Thanks for that! Next up — {next_q}",
                "tools_used": [], "memory_updated": False,
                "knowledge_recalled": [], "onboarding": True,
            }

        # Parse the JSON control block from LLM response
        import json as _json
        display_text = response_text
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                control = _json.loads(json_match.group(1))
                # Remove JSON block from displayed text
                display_text = response_text[:json_match.start()].strip()

                # Extract any info the LLM found
                extracted = control.get("extracted_info", {})
                if extracted:
                    for key, value in extracted.items():
                        # Find matching question by knowledge_key
                        for q in ONBOARDING_QUESTIONS:
                            if q["knowledge_key"].lower() == key.lower() or q["id"] == key.lower():
                                state["answers"][q["id"]] = {
                                    "question": q["question"],
                                    "answer": str(value),
                                    "knowledge_key": q["knowledge_key"],
                                    "category": q["category"],
                                }
                                break

                # Advance to next question if appropriate
                if control.get("advance", False) or control.get("answered_current", False):
                    state["current_question_idx"] = current_idx + 1
        except (_json.JSONDecodeError, AttributeError):
            # No valid JSON — just advance if the message looks like an answer
            if len(message.strip()) > 2 and message.strip().lower() not in ("?", "ok"):
                if current_q:
                    state["answers"][current_q["id"]] = {
                        "question": current_q["question"],
                        "answer": message,
                        "knowledge_key": current_q["knowledge_key"],
                        "category": current_q["category"],
                    }
                state["current_question_idx"] = current_idx + 1

        # Check if onboarding is complete
        if state["current_question_idx"] >= len(ONBOARDING_QUESTIONS):
            state["completed"] = True
            state["active"] = False
            await self.onboarding.save_profile(state)
            completion_msg = self.onboarding.get_completion_message(state["answers"])
            await self.memory.set_working("onboarding_state", None)
            logger.info("Onboarding completed!")
            return {
                "text": display_text + "\n\n" + completion_msg if display_text else completion_msg,
                "tools_used": [], "memory_updated": True,
                "knowledge_recalled": [], "onboarding": True,
            }

        await self.memory.set_working("onboarding_state", state)

        return {
            "text": display_text or response_text,
            "tools_used": [],
            "memory_updated": False,
            "knowledge_recalled": [],
            "onboarding": True,
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

        # Load knowledge from community SKILL.md files (instructions for tools/integrations)
        self._inject_skill_knowledge(prompt_parts)

        return "\n".join(prompt_parts)

    def _build_messages(
        self,
        system_prompt: str,
        conversation: list[dict],
        memories: list[dict],
        current_message: str,
        images: list[str] | None = None,
    ) -> list[dict]:
        """Build the full message list for the LLM.

        Args:
            images: Optional list of file paths to images (for vision models).
        """
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

        # Add current message (with images if provided)
        if images:
            # Multi-modal message: text + images (OpenAI Vision format)
            content_parts = []
            if current_message:
                content_parts.append({"type": "text", "text": current_message})
            for img_path in images:
                image_data = self._encode_image(img_path)
                if image_data:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": image_data},
                    })
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": current_message})

        return messages

    def _encode_image(self, image_path: str) -> str | None:
        """Encode an image file to a base64 data URL for vision APIs."""
        import base64
        from pathlib import Path

        path = Path(image_path)
        if not path.exists():
            logger.warning(f"Image not found: {image_path}")
            return None

        # Determine MIME type
        ext = path.suffix.lower()
        mime_types = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/png")

        try:
            data = base64.b64encode(path.read_bytes()).decode("utf-8")
            return f"data:{mime_type};base64,{data}"
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            return None

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

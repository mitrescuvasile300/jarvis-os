"""Agent Manager — Spawn, manage, and communicate with sub-agents.

Each sub-agent is a lightweight JarvisAgent running in an asyncio task
with its own:
- LLM client (can be different model)
- Tool subset
- Conversation memory
- System prompt (specialized for its role)

Jarvis (the orchestrator) communicates with agents via a task queue:
- Jarvis sends tasks → agent processes → reports results
- Each agent has a status: idle, working, stopped
- Agents persist across conversations (state saved to disk)

Architecture:
  Jarvis ←→ AgentManager ←→ [Agent1, Agent2, Agent3, ...]
                ↕
         persistent/agents/  (agent configs + state)
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.agent_manager")

# Agent templates with default configurations
AGENT_TEMPLATES = {
    "research": {
        "description": "Deep web research, article summarization, trend analysis",
        "system_prompt": (
            "You are a Research Agent. Your job is to thoroughly research topics "
            "using web search and browsing. Always cite sources. Be comprehensive "
            "but organized. Use bullet points and headers."
        ),
        "tools": ["web_search", "browse", "screenshot", "read_file", "write_file", "run_code"],
        "default_model": None,  # inherits from Jarvis
    },
    "trading": {
        "description": "Crypto market scanning, token analysis, trading signals",
        "system_prompt": (
            "You are a Trading Agent specialized in crypto/Solana analysis. "
            "Use web search and browsing to check token metrics, social presence, "
            "and market data. Be data-driven. Always show numbers."
        ),
        "tools": ["web_search", "browse", "screenshot", "http_request", "run_code", "read_file", "write_file"],
        "default_model": None,
    },
    "content": {
        "description": "Writing, editing, social media, content creation",
        "system_prompt": (
            "You are a Content Agent. You help create, edit, and improve written "
            "content. You can research topics, write drafts, and iterate. "
            "Match the user's tone and style."
        ),
        "tools": ["web_search", "browse", "read_file", "write_file", "run_code"],
        "default_model": None,
    },
    "devops": {
        "description": "Infrastructure, deployment, monitoring, system administration",
        "system_prompt": (
            "You are a DevOps Agent. You help with infrastructure, deployments, "
            "monitoring, and system administration. Use shell commands and code "
            "execution. Be precise and safe."
        ),
        "tools": ["shell_command", "run_code", "read_file", "write_file", "http_request", "browse", "search_files"],
        "default_model": None,
    },
    "custom": {
        "description": "General-purpose agent with all tools",
        "system_prompt": "You are a specialized AI agent. Follow your instructions carefully.",
        "tools": None,  # all tools
        "default_model": None,
    },
}


class SubAgent:
    """A spawned sub-agent with its own LLM, tools, and memory."""

    def __init__(self, agent_id: str, config: dict, llm_client, tool_registry):
        self.id = agent_id
        self.name = config["name"]
        self.template = config.get("template", "custom")
        self.model = config.get("model", "")
        self.system_prompt = config.get("system_prompt", "")
        self.personality = config.get("personality", "")
        self.status = "idle"  # idle, working, stopped
        self.created_at = config.get("created_at", datetime.now().isoformat())

        self.llm = llm_client
        self.tool_registry = tool_registry
        self.allowed_tools = config.get("tools")  # None = all tools

        # Conversation history (in-memory, persisted to disk)
        self.conversation: list[dict] = config.get("conversation", [])

        # Task queue
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._current_task: dict | None = None
        self._worker_task: asyncio.Task | None = None
        self._results: list[dict] = []

    def to_dict(self) -> dict:
        """Serialize agent state for persistence and API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "template": self.template,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "personality": self.personality,
            "status": self.status,
            "created_at": self.created_at,
            "tools": self.allowed_tools,
            "conversation_length": len(self.conversation),
            "pending_tasks": self._task_queue.qsize(),
        }

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions filtered by allowed tools."""
        all_tools = self.tool_registry.get_definitions()
        if self.allowed_tools is None:
            return all_tools
        return [t for t in all_tools if t["name"] in self.allowed_tools]

    async def chat(self, message: str) -> dict:
        """Process a direct chat message to this agent."""
        self.status = "working"

        try:
            # Build messages
            messages = [{"role": "system", "content": self._build_system_prompt()}]

            # Add conversation history (last 20)
            for msg in self.conversation[-20:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

            messages.append({"role": "user", "content": message})

            # Get available tools
            tool_defs = self.get_tool_definitions()

            # Call LLM
            response = await self.llm.chat(
                messages=messages,
                tools=tool_defs if tool_defs else None,
                temperature=0.7,
                max_tokens=4096,
            )

            response_text = response.get("text") or ""

            # Handle tool calls (single round for sub-agents)
            tools_used = []
            if response.get("tool_calls"):
                tool_results = []
                for tc in response["tool_calls"]:
                    tool_name = tc["name"]
                    if self.allowed_tools and tool_name not in self.allowed_tools:
                        tool_results.append(f"{tool_name}: not allowed for this agent")
                        continue

                    try:
                        result = await self.tool_registry.execute(tool_name, tc["arguments"])
                        tool_results.append(f"{tool_name}: {str(result)[:1000]}")
                        tools_used.append(tool_name)
                    except Exception as e:
                        tool_results.append(f"{tool_name}: error - {e}")
                        tools_used.append(f"{tool_name}(failed)")

                # Get final response with tool results
                messages.append({"role": "assistant", "content": response_text or ""})
                messages.append({
                    "role": "system",
                    "content": "Tool results:\n" + "\n".join(tool_results),
                })

                try:
                    follow_up = await self.llm.chat(
                        messages=messages, temperature=0.7, max_tokens=4096,
                    )
                    response_text = follow_up.get("text") or response_text
                except Exception as e:
                    logger.error(f"[{self.name}] Follow-up LLM failed: {e}")
                    response_text = f"Tool results:\n" + "\n".join(tool_results)

            if not response_text:
                response_text = "I processed the request but couldn't generate a response."

            # Store conversation
            self.conversation.append({"role": "user", "content": message, "ts": datetime.now().isoformat()})
            self.conversation.append({"role": "assistant", "content": response_text, "ts": datetime.now().isoformat()})

            return {
                "text": response_text,
                "tools_used": tools_used,
                "agent_id": self.id,
                "agent_name": self.name,
            }

        except Exception as e:
            logger.error(f"[{self.name}] Chat error: {e}")
            return {"text": f"Error: {e}", "tools_used": [], "agent_id": self.id, "agent_name": self.name}

        finally:
            self.status = "idle"

    async def execute_task(self, task: dict) -> dict:
        """Execute a task from Jarvis."""
        task_type = task.get("type", "chat")
        task_content = task.get("content", "")
        task_id = task.get("id", str(uuid.uuid4())[:8])

        logger.info(f"[{self.name}] Executing task {task_id}: {task_content[:80]}...")
        self._current_task = task

        result = await self.chat(task_content)
        result["task_id"] = task_id
        result["task_type"] = task_type

        self._current_task = None
        self._results.append(result)

        return result

    def _build_system_prompt(self) -> str:
        """Build the agent's system prompt."""
        parts = [self.system_prompt]
        if self.personality:
            parts.append(f"\nPersonality: {self.personality}")

        # List available tools
        tool_defs = self.get_tool_definitions()
        if tool_defs:
            parts.append("\nYour available tools:")
            for t in tool_defs:
                parts.append(f"- {t['name']}: {t['description']}")
            parts.append("\nUse these tools when they can help accomplish the task.")

        return "\n".join(parts)


class AgentManager:
    """Manages all sub-agents — create, delete, communicate, persist."""

    def __init__(self, llm_client, tool_registry, config: dict):
        self.llm = llm_client
        self.tools = tool_registry
        self.config = config
        self.agents: dict[str, SubAgent] = {}
        from jarvis import workspace
        self._agents_dir = workspace.path("data", "agents")
        self._agents_dir.mkdir(parents=True, exist_ok=True)

    async def create_agent(
        self,
        name: str,
        template: str = "custom",
        model: str | None = None,
        system_prompt: str | None = None,
        personality: str = "",
        tools: list[str] | None = None,
    ) -> SubAgent:
        """Create and register a new sub-agent."""
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"

        # Get template defaults
        tmpl = AGENT_TEMPLATES.get(template, AGENT_TEMPLATES["custom"])

        agent_config = {
            "name": name,
            "template": template,
            "model": model or self.config.get("agent", {}).get("llm", {}).get("model", ""),
            "system_prompt": system_prompt or tmpl["system_prompt"],
            "personality": personality,
            "tools": tools or tmpl.get("tools"),
            "created_at": datetime.now().isoformat(),
            "conversation": [],
        }

        agent = SubAgent(agent_id, agent_config, self.llm, self.tools)
        self.agents[agent_id] = agent

        # Persist config
        self._save_agent(agent_id, agent_config)

        logger.info(f"Created agent: {name} ({template}) id={agent_id}")
        return agent

    def get_agent(self, agent_id: str) -> SubAgent | None:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def list_agents(self) -> list[dict]:
        """List all agents with their status."""
        return [agent.to_dict() for agent in self.agents.values()]

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        agent = self.agents.pop(agent_id, None)
        if not agent:
            return False

        agent.status = "stopped"

        # Remove persisted state
        agent_file = self._agents_dir / f"{agent_id}.json"
        if agent_file.exists():
            agent_file.unlink()

        logger.info(f"Deleted agent: {agent.name} ({agent_id})")
        return True

    async def send_task(self, agent_id: str, task_content: str, task_type: str = "chat") -> dict:
        """Send a task to an agent and get the result."""
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}

        if agent.status == "stopped":
            return {"error": f"Agent {agent.name} is stopped"}

        task = {
            "id": str(uuid.uuid4())[:8],
            "type": task_type,
            "content": task_content,
            "from": "jarvis",
            "timestamp": datetime.now().isoformat(),
        }

        result = await agent.execute_task(task)

        # Save conversation state after task
        self._save_agent_state(agent_id)

        return result

    async def chat_with_agent(self, agent_id: str, message: str) -> dict:
        """Direct chat with an agent (from the UI)."""
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found", "text": "Agent not found."}

        result = await agent.chat(message)

        # Save state
        self._save_agent_state(agent_id)

        return result

    def load_persisted_agents(self):
        """Load agents from disk on startup."""
        loaded = 0
        for agent_file in self._agents_dir.glob("agent_*.json"):
            try:
                config = json.loads(agent_file.read_text(encoding="utf-8"))
                agent_id = agent_file.stem
                agent = SubAgent(agent_id, config, self.llm, self.tools)
                self.agents[agent_id] = agent
                loaded += 1
            except Exception as e:
                logger.error(f"Failed to load agent {agent_file}: {e}")

        if loaded:
            logger.info(f"Loaded {loaded} persisted agents")

    def _save_agent(self, agent_id: str, config: dict):
        """Save agent config to disk."""
        agent_file = self._agents_dir / f"{agent_id}.json"
        agent_file.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")

    def _save_agent_state(self, agent_id: str):
        """Save agent's current state (including conversation)."""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        config = {
            "name": agent.name,
            "template": agent.template,
            "model": agent.model,
            "system_prompt": agent.system_prompt,
            "personality": agent.personality,
            "tools": agent.allowed_tools,
            "created_at": agent.created_at,
            "conversation": agent.conversation[-50:],  # Keep last 50 messages
        }
        self._save_agent(agent_id, config)

    def get_templates(self) -> dict:
        """Get available agent templates."""
        return {
            name: {"name": name, "description": tmpl["description"]}
            for name, tmpl in AGENT_TEMPLATES.items()
        }

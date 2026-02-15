"""Jarvis OS — HTTP Server with REST API and Dashboard.

Serves:
- Dashboard UI at /
- REST API at /api/*
- Health check at /health
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime
from pathlib import Path

from aiohttp import web

from jarvis.agent import JarvisAgent
from jarvis.config import load_config
from jarvis.websocket_handler import ChatWebSocket
from jarvis.plugins import PluginLoader

logger = logging.getLogger("jarvis.server")


class JarvisServer:
    def __init__(self):
        self.config = load_config()
        self.agent = JarvisAgent(self.config)
        self.ws_handler = ChatWebSocket(self.agent)
        self.plugin_loader = PluginLoader()
        self.started_at = datetime.now()

    async def initialize(self):
        """Initialize the agent and all components."""
        await self.agent.initialize()

        # Load plugins
        plugins = self.plugin_loader.load_all()
        if plugins:
            logger.info(f"Loaded {len(plugins)} plugin tool(s): {list(plugins.keys())}")

        logger.info(f"Agent '{self.agent.name}' initialized")

    def create_app(self) -> web.Application:
        """Create the aiohttp application."""
        app = web.Application()

        # Dashboard routes
        app.router.add_get("/", self.handle_dashboard)
        app.router.add_static("/static", self._dashboard_static_path(), name="static")

        # WebSocket
        app.router.add_get("/ws/chat", self.ws_handler.handle)

        # API routes
        app.router.add_get("/health", self.handle_health)
        app.router.add_post("/api/chat", self.handle_chat)
        app.router.add_get("/api/status", self.handle_status)
        app.router.add_get("/api/memory/search", self.handle_memory_search)
        app.router.add_get("/api/knowledge", self.handle_knowledge)
        app.router.add_get("/api/knowledge/stats", self.handle_knowledge_stats)
        app.router.add_post("/api/knowledge/consolidate", self.handle_knowledge_consolidate)
        app.router.add_get("/api/skills", self.handle_skills)
        app.router.add_post("/api/skills/{name}/run", self.handle_skill_run)
        app.router.add_get("/api/tools", self.handle_tools)
        app.router.add_post("/api/agents", self.handle_create_agent)
        app.router.add_get("/api/agents", self.handle_list_agents)
        app.router.add_post("/api/settings/keys", self.handle_save_key)
        app.router.add_get("/api/plugins", self.handle_list_plugins)
        app.router.add_post("/api/plugins/{name}/run", self.handle_run_plugin)

        return app

    def _dashboard_static_path(self) -> str:
        """Find the dashboard static files."""
        # Check multiple locations
        candidates = [
            Path(__file__).parent.parent / "dashboard" / "static",
            Path("dashboard") / "static",
            Path("/app/dashboard/static"),
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        # Create a minimal fallback
        fallback = Path("dashboard/static")
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)

    # ── Dashboard ────────────────────────────────────────────

    async def handle_dashboard(self, request: web.Request) -> web.Response:
        """Serve the dashboard HTML."""
        candidates = [
            Path(__file__).parent.parent / "dashboard" / "index.html",
            Path("dashboard") / "index.html",
            Path("/app/dashboard/index.html"),
        ]
        for path in candidates:
            if path.exists():
                return web.FileResponse(path)

        return web.Response(
            text="<h1>Jarvis OS</h1><p>Dashboard not found. API is running at /api/*</p>",
            content_type="text/html",
        )

    # ── API Handlers ─────────────────────────────────────────

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        uptime = int((datetime.now() - self.started_at).total_seconds())
        memory_count = await self.agent.memory.count()
        knowledge_files = len(self.agent.knowledge.get_all_knowledge()) if self.agent.knowledge else 0

        return web.json_response({
            "status": "healthy",
            "agent": self.agent.name,
            "version": "1.1.0",
            "uptime_seconds": uptime,
            "memory_entries": memory_count,
            "knowledge_files": knowledge_files,
            "skills_loaded": len(self.agent.skills),
            "tools_available": len(self.agent.tools.list()),
        })

    async def handle_chat(self, request: web.Request) -> web.Response:
        """Chat with the agent."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = data.get("message", "").strip()
        if not message:
            return web.json_response({"error": "Message is required"}, status=400)

        conversation_id = data.get("conversation_id", "api")

        try:
            response = await self.agent.chat(message, conversation_id=conversation_id)
            return web.json_response({
                "text": response.get("text", ""),
                "tools_used": response.get("tools_used", []),
                "conversation_id": conversation_id,
            })
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_status(self, request: web.Request) -> web.Response:
        """Detailed agent status."""
        uptime = int((datetime.now() - self.started_at).total_seconds())
        memory_count = await self.agent.memory.count()

        return web.json_response({
            "agent": {
                "name": self.agent.name,
                "model": self.config["agent"]["llm"]["model"],
                "provider": self.config["agent"]["llm"]["provider"],
            },
            "uptime_seconds": uptime,
            "memory": {"entries": memory_count},
            "skills": list(self.agent.skills.keys()),
            "tools": self.agent.tools.list(),
        })

    async def handle_memory_search(self, request: web.Request) -> web.Response:
        """Search agent memory."""
        query = request.query.get("q", "")
        limit = int(request.query.get("limit", "10"))

        if not query:
            return web.json_response({"error": "Query parameter 'q' is required"}, status=400)

        results = await self.agent.memory.search(query, limit=limit)
        return web.json_response({"query": query, "results": results})

    async def handle_skills(self, request: web.Request) -> web.Response:
        """List available skills (built-in + community)."""
        skills = []

        # Built-in skills (with actions)
        for name, skill in self.agent.skills.items():
            skills.append({
                "name": name,
                "description": skill.description,
                "actions": list(skill.actions.keys()),
                "enabled": skill.enabled,
                "type": "built-in",
            })

        # Community skills (knowledge-based from SKILL.md)
        from pathlib import Path
        community_dir = Path("skills-community")
        if community_dir.exists():
            enabled_list = self.config.get("skills", {}).get("enabled", [])
            for skill_dir in sorted(community_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue

                # Parse description from frontmatter
                desc = ""
                try:
                    content = skill_md.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        for line in content.split("\n")[1:20]:
                            if line.strip() == "---":
                                break
                            if line.startswith("description:"):
                                desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                except Exception:
                    pass

                name = skill_dir.name
                # Skip if already listed as built-in
                if any(s["name"] == name for s in skills):
                    continue

                skills.append({
                    "name": name,
                    "description": desc or f"{name} community skill",
                    "actions": [],
                    "enabled": name in enabled_list or not enabled_list,
                    "type": "community",
                    "source": "clawhub",
                })

        return web.json_response({"skills": skills, "total": len(skills)})

    async def handle_skill_run(self, request: web.Request) -> web.Response:
        """Execute a skill action."""
        skill_name = request.match_info["name"]
        try:
            data = await request.json()
        except Exception:
            data = {}

        action = data.get("action", "default")
        params = data.get("params", {})

        try:
            result = await self.agent.run_skill(skill_name, action, params)
            return web.json_response({"result": str(result)})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_tools(self, request: web.Request) -> web.Response:
        """List available tools."""
        return web.json_response({
            "tools": self.agent.tools.get_definitions(),
        })

    async def handle_create_agent(self, request: web.Request) -> web.Response:
        """Create a new agent workspace."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        name = data.get("name", "").strip()
        template = data.get("template", "custom")

        if not name:
            return web.json_response({"error": "Name is required"}, status=400)

        try:
            from jarvis.init_command import create_agent_workspace
            path = create_agent_workspace(name, template)
            return web.json_response({"success": True, "workspace": path})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_list_agents(self, request: web.Request) -> web.Response:
        """List agent workspaces."""
        workspaces = []
        for d in Path(".").iterdir():
            config = d / "agent.config.json"
            if d.is_dir() and config.exists():
                try:
                    c = json.loads(config.read_text())
                    workspaces.append({
                        "name": c.get("name", d.name),
                        "template": c.get("template", "custom"),
                        "model": c.get("model", "unknown"),
                        "path": str(d),
                    })
                except Exception:
                    pass
        return web.json_response({"agents": workspaces})

    async def handle_list_plugins(self, request: web.Request) -> web.Response:
        """List loaded plugins."""
        registry = self.plugin_loader.get_registry()
        plugins = []
        for name, info in registry.items():
            plugins.append({
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"],
                "source": os.path.basename(info.get("source", "")),
            })
        return web.json_response({"plugins": plugins})

    async def handle_run_plugin(self, request: web.Request) -> web.Response:
        """Execute a plugin tool."""
        name = request.match_info["name"]
        try:
            data = await request.json()
        except Exception:
            data = {}

        try:
            result = await self.plugin_loader.execute_tool(name, **data)
            return web.json_response({"result": str(result)})
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=404)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ── Knowledge Endpoints ────────────────────────────────────

    async def handle_knowledge(self, request: web.Request) -> web.Response:
        """List all knowledge files and their content."""
        if not self.agent.knowledge:
            return web.json_response({"error": "Knowledge system not initialized"}, status=500)

        knowledge = self.agent.knowledge.get_all_knowledge()
        files = []
        for filename, content in knowledge.items():
            files.append({
                "filename": filename,
                "content": content,
                "size_chars": len(content),
            })
        return web.json_response({"files": files})

    async def handle_knowledge_stats(self, request: web.Request) -> web.Response:
        """Get knowledge system statistics."""
        stats = await self.agent.get_knowledge_stats()
        return web.json_response(stats)

    async def handle_knowledge_consolidate(self, request: web.Request) -> web.Response:
        """Trigger knowledge consolidation (dedup, merge, cleanup)."""
        try:
            await self.agent.consolidate_knowledge()
            return web.json_response({"success": True, "message": "Knowledge consolidated"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_save_key(self, request: web.Request) -> web.Response:
        """Save an API key or model setting to .env and apply live."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        provider = data.get("provider", "")
        key = data.get("key", "")
        model = data.get("model", "")

        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
            "ollama": "OLLAMA_URL",
            "slack": "SLACK_BOT_TOKEN",
            "twitter": "TWITTER_API_KEY",
            "github": "GITHUB_TOKEN",
        }

        env_var = env_map.get(provider)
        if not env_var:
            return web.json_response({"error": f"Unknown provider: {provider}"}, status=400)

        # Set in environment
        if key:
            os.environ[env_var] = key

        # Persist to .env
        env_file = Path(".env")
        if env_file.exists():
            content = env_file.read_text()
        else:
            content = ""

        # Update API key in .env
        if key:
            import re
            if f"{env_var}=" in content:
                content = re.sub(f"{env_var}=.*", f"{env_var}={key}", content)
            else:
                content += f"\n{env_var}={key}"

        # Update model in .env if provided
        if model:
            import re
            model_var = f"{provider.upper()}_MODEL"
            os.environ[model_var] = model
            if f"{model_var}=" in content:
                content = re.sub(f"{model_var}=.*", f"{model_var}={model}", content)
            else:
                content += f"\n{model_var}={model}"

        if content:
            env_file.write_text(content)

        # ── HOT RELOAD: Apply changes to running agent ──
        try:
            if key or model:
                # Update in-memory config
                if provider in ("openai", "anthropic", "ollama"):
                    if key:
                        self.config["agent"]["llm"][f"{provider}_api_key"] = key
                    if model:
                        self.config["agent"]["llm"]["model"] = model
                        self.config["agent"]["llm"]["provider"] = provider

                    # Reinitialize LLM client with new config
                    from jarvis.llm import create_llm_client
                    self.agent.llm = create_llm_client(self.config["agent"]["llm"])
                    logger.info(f"LLM hot-reloaded: {provider} / {model or 'same model'}")

        except Exception as e:
            logger.warning(f"Hot reload failed (will apply on restart): {e}")

        return web.json_response({"success": True})


def main():
    """Start the Jarvis server."""
    logging.basicConfig(
        level=getattr(logging, os.getenv("AGENT_LOG_LEVEL", "INFO")),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    server = JarvisServer()
    app = server.create_app()

    host = server.config["server"]["host"]
    port = server.config["server"]["port"]

    async def on_startup(app):
        await server.initialize()

    app.on_startup.append(on_startup)

    logger.info(f"Starting Jarvis OS on {host}:{port}")
    logger.info(f"Dashboard: http://localhost:{port}")
    logger.info(f"API: http://localhost:{port}/api")

    web.run_app(app, host=host, port=port, print=lambda x: logger.info(x))


if __name__ == "__main__":
    main()

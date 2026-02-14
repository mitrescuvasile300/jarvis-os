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

logger = logging.getLogger("jarvis.server")


class JarvisServer:
    def __init__(self):
        self.config = load_config()
        self.agent = JarvisAgent(self.config)
        self.started_at = datetime.now()

    async def initialize(self):
        """Initialize the agent and all components."""
        await self.agent.initialize()
        logger.info(f"Agent '{self.agent.name}' initialized")

    def create_app(self) -> web.Application:
        """Create the aiohttp application."""
        app = web.Application()

        # Dashboard routes
        app.router.add_get("/", self.handle_dashboard)
        app.router.add_static("/static", self._dashboard_static_path(), name="static")

        # API routes
        app.router.add_get("/health", self.handle_health)
        app.router.add_post("/api/chat", self.handle_chat)
        app.router.add_get("/api/status", self.handle_status)
        app.router.add_get("/api/memory/search", self.handle_memory_search)
        app.router.add_get("/api/skills", self.handle_skills)
        app.router.add_post("/api/skills/{name}/run", self.handle_skill_run)
        app.router.add_get("/api/tools", self.handle_tools)
        app.router.add_post("/api/agents", self.handle_create_agent)
        app.router.add_get("/api/agents", self.handle_list_agents)
        app.router.add_post("/api/settings/keys", self.handle_save_key)

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

        return web.json_response({
            "status": "healthy",
            "agent": self.agent.name,
            "version": "1.0.0",
            "uptime_seconds": uptime,
            "memory_entries": memory_count,
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
        """List available skills."""
        skills = []
        for name, skill in self.agent.skills.items():
            skills.append({
                "name": name,
                "description": skill.description,
                "actions": list(skill.actions.keys()),
                "enabled": skill.enabled,
            })
        return web.json_response({"skills": skills})

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

    async def handle_save_key(self, request: web.Request) -> web.Response:
        """Save an API key to .env."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        provider = data.get("provider", "")
        key = data.get("key", "")

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
        os.environ[env_var] = key

        # Persist to .env if it exists
        env_file = Path(".env")
        if env_file.exists():
            content = env_file.read_text()
            if f"{env_var}=" in content:
                import re
                content = re.sub(f"{env_var}=.*", f"{env_var}={key}", content)
            else:
                content += f"\n{env_var}={key}"
            env_file.write_text(content)

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

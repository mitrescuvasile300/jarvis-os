"""Jarvis OS — HTTP API Server.

Exposes a REST API for interacting with the Jarvis agent.
Supports chat, memory queries, skill execution, and health checks.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime

from aiohttp import web

from jarvis.agent import JarvisAgent
from jarvis.config import load_config

logger = logging.getLogger("jarvis.server")


class JarvisServer:
    def __init__(self):
        self.config = load_config()
        self.agent = JarvisAgent(self.config)
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/health", self.health)
        self.app.router.add_post("/api/chat", self.chat)
        self.app.router.add_get("/api/memory/search", self.memory_search)
        self.app.router.add_get("/api/skills", self.list_skills)
        self.app.router.add_post("/api/skills/{skill}/run", self.run_skill)
        self.app.router.add_get("/api/status", self.status)

    def _check_auth(self, request: web.Request) -> bool:
        """Validate API key if configured."""
        api_key = self.config.get("agent", {}).get("api_key", "")
        if not api_key:
            return True
        auth_header = request.headers.get("Authorization", "")
        return auth_header == f"Bearer {api_key}"

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "healthy",
            "agent": self.config["agent"]["name"],
            "version": "1.0.0",
            "uptime_seconds": int((datetime.now() - self.agent.started_at).total_seconds()),
            "memory_entries": await self.agent.memory.count(),
            "skills_loaded": len(self.agent.skills),
        })

    async def chat(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = body.get("message", "").strip()
        if not message:
            return web.json_response({"error": "Message is required"}, status=400)

        conversation_id = body.get("conversation_id", "default")

        response = await self.agent.chat(message, conversation_id=conversation_id)

        return web.json_response({
            "response": response["text"],
            "conversation_id": conversation_id,
            "tools_used": response.get("tools_used", []),
            "memory_updated": response.get("memory_updated", False),
            "timestamp": datetime.now().isoformat(),
        })

    async def memory_search(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        query = request.query.get("q", "")
        limit = int(request.query.get("limit", "10"))

        if not query:
            return web.json_response({"error": "Query parameter 'q' is required"}, status=400)

        results = await self.agent.memory.search(query, limit=limit)
        return web.json_response({"results": results, "query": query})

    async def list_skills(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        skills = []
        for name, skill in self.agent.skills.items():
            skills.append({
                "name": name,
                "description": skill.description,
                "actions": list(skill.actions.keys()),
                "enabled": skill.enabled,
            })
        return web.json_response({"skills": skills})

    async def run_skill(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        skill_name = request.match_info["skill"]
        body = await request.json() if request.content_length else {}
        action = body.get("action", "default")
        params = body.get("params", {})

        try:
            result = await self.agent.run_skill(skill_name, action, params)
            return web.json_response({"result": result, "skill": skill_name, "action": action})
        except KeyError:
            return web.json_response({"error": f"Skill '{skill_name}' not found"}, status=404)
        except Exception as e:
            logger.exception(f"Skill execution failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def status(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        return web.json_response({
            "agent": self.config["agent"]["name"],
            "version": "1.0.0",
            "llm_provider": self.config["agent"]["llm"]["provider"],
            "llm_model": self.config["agent"]["llm"]["model"],
            "memory_backend": self.config["memory"]["backend"],
            "vector_store": self.config["memory"]["vector_store"],
            "skills": list(self.agent.skills.keys()),
            "integrations": list(self.agent.integrations.keys()),
            "uptime_seconds": int((datetime.now() - self.agent.started_at).total_seconds()),
        })

    async def start(self):
        """Initialize agent and start server."""
        logger.info(f"Starting Jarvis OS v1.0.0 — agent: {self.config['agent']['name']}")
        await self.agent.initialize()

        runner = web.AppRunner(self.app)
        await runner.setup()

        host = self.config.get("server", {}).get("host", "0.0.0.0")
        port = self.config.get("server", {}).get("port", 8080)

        site = web.TCPSite(runner, host, port)
        await site.start()

        logger.info(f"Jarvis OS running at http://{host}:{port}")
        logger.info(f"LLM: {self.config['agent']['llm']['provider']} / {self.config['agent']['llm']['model']}")
        logger.info(f"Skills loaded: {', '.join(self.agent.skills.keys()) or 'none'}")
        logger.info(f"Integrations: {', '.join(self.agent.integrations.keys()) or 'none'}")

        # Keep running
        stop_event = asyncio.Event()

        def _handle_signal():
            logger.info("Shutdown signal received")
            stop_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_signal)

        await stop_event.wait()
        logger.info("Shutting down Jarvis OS...")
        await self.agent.shutdown()
        await runner.cleanup()


def main():
    logging.basicConfig(
        level=getattr(logging, os.getenv("AGENT_LOG_LEVEL", "INFO")),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    server = JarvisServer()
    asyncio.run(server.start())


if __name__ == "__main__":
    main()

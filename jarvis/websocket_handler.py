"""WebSocket handler for real-time agent chat streaming.

Provides token-by-token streaming responses like ChatGPT.
Protocol:
  Client sends: {"type": "message", "agent_id": "...", "text": "..."}
  Server sends: {"type": "token", "text": "..."} (repeated)
  Server sends: {"type": "done", "tools_used": [...]}
  Server sends: {"type": "error", "message": "..."}
"""

import asyncio
import json
import logging
from typing import Optional

import aiohttp
from aiohttp import web

logger = logging.getLogger("jarvis.ws")


class ChatWebSocket:
    """Manages WebSocket connections for Jarvis + sub-agent chats."""

    def __init__(self, agent):
        self.agent = agent
        self.agent_manager = None  # Set by server after init
        self.connections: dict[str, list[web.WebSocketResponse]] = {}  # agent_id -> [ws]

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        """Handle a new WebSocket connection."""
        ws = web.WebSocketResponse(heartbeat=30.0)
        await ws.prepare(request)

        agent_id = request.query.get("agent_id", "default")
        logger.info(f"WebSocket connected for agent: {agent_id}")

        # Track connection
        if agent_id not in self.connections:
            self.connections[agent_id] = []
        self.connections[agent_id].append(ws)

        # Send welcome
        await ws.send_json({
            "type": "connected",
            "agent_id": agent_id,
            "agent_name": self.agent.name,
        })

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(ws, msg.data, agent_id)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            # Remove connection
            if agent_id in self.connections:
                self.connections[agent_id] = [
                    c for c in self.connections[agent_id] if c != ws
                ]
            logger.info(f"WebSocket disconnected for agent: {agent_id}")

        return ws

    async def _handle_message(self, ws: web.WebSocketResponse, raw: str, agent_id: str):
        """Process an incoming WebSocket message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send_json({"type": "error", "message": "Invalid JSON"})
            return

        msg_type = data.get("type", "")

        if msg_type == "message":
            await self._handle_chat(ws, data, agent_id)
        elif msg_type == "ping":
            await ws.send_json({"type": "pong"})
        else:
            await ws.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    async def _handle_chat(self, ws: web.WebSocketResponse, data: dict, agent_id: str):
        """Handle a chat message — routes to Jarvis or sub-agent."""
        text = data.get("text", "").strip()
        image_ids = data.get("images", [])
        target_agent = data.get("agent_id", "jarvis")  # "jarvis" or "agent_xxx"

        if not text and not image_ids:
            await ws.send_json({"type": "error", "message": "Empty message"})
            return

        # Route to sub-agent if target is not jarvis
        if target_agent and target_agent != "jarvis" and target_agent.startswith("agent_"):
            await self._handle_agent_chat(ws, text, target_agent)
            return

        # Default: Jarvis chat
        await self._handle_jarvis_chat(ws, data, agent_id, text, image_ids)

    async def _handle_jarvis_chat(
        self, ws, data: dict, agent_id: str, text: str, image_ids: list
    ):
        """Handle chat with Jarvis (main agent)."""
        conversation_id = data.get("conversation_id", f"ws_{agent_id}")
        image_paths = self._resolve_image_paths(image_ids)

        await ws.send_json({"type": "thinking", "text": "Processing..."})

        try:
            tools_used = []
            full_response = ""

            if hasattr(self.agent, "chat_stream"):
                async for chunk in self.agent.chat_stream(
                    text, conversation_id=conversation_id, images=image_paths
                ):
                    if chunk.get("type") == "token":
                        token = chunk["text"]
                        full_response += token
                        await ws.send_json({"type": "token", "text": token})
                    elif chunk.get("type") == "tool_call":
                        tool_name = chunk.get("tool", "unknown")
                        tools_used.append(tool_name)
                        await ws.send_json({
                            "type": "tool_call",
                            "tool": tool_name,
                            "status": chunk.get("status", "running"),
                        })
            else:
                response = await self.agent.chat(
                    text, conversation_id=conversation_id, images=image_paths
                )
                full_response = response.get("text") or ""
                tools_used = response.get("tools_used", [])

                logger.info(
                    f"Jarvis response: {len(full_response)} chars, "
                    f"tools={tools_used}, preview={full_response[:100]!r}"
                )

                if not full_response.strip():
                    full_response = "I processed your request but couldn't generate a response. Check the logs for details."

                # Simulate streaming
                words = full_response.split(" ")
                for i, word in enumerate(words):
                    token = word + (" " if i < len(words) - 1 else "")
                    await ws.send_json({"type": "token", "text": token})
                    await asyncio.sleep(0.02)

            # Check if Jarvis spawned an agent (notify frontend to refresh)
            if any(t in ["spawn_agent"] for t in tools_used):
                agents = self.agent_manager.list_agents() if self.agent_manager else []
                await ws.send_json({"type": "agents_updated", "agents": agents})

            await ws.send_json({
                "type": "done",
                "full_text": full_response,
                "tools_used": tools_used,
            })

        except Exception as e:
            logger.error(f"Jarvis chat error: {e}")
            await ws.send_json({"type": "error", "message": str(e)})

    async def _handle_agent_chat(self, ws, text: str, agent_id: str):
        """Handle chat with a sub-agent via WebSocket."""
        if not self.agent_manager:
            await ws.send_json({"type": "error", "message": "Agent manager not ready"})
            return

        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            await ws.send_json({"type": "error", "message": f"Agent '{agent_id}' not found"})
            return

        await ws.send_json({"type": "thinking", "text": f"{agent.name} is thinking..."})

        try:
            result = await self.agent_manager.chat_with_agent(agent_id, text)
            full_response = result.get("text") or "No response."
            tools_used = result.get("tools_used", [])

            logger.info(
                f"Agent '{agent.name}' response: {len(full_response)} chars, tools={tools_used}"
            )

            # Simulate streaming
            words = full_response.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                await ws.send_json({"type": "token", "text": token})
                await asyncio.sleep(0.02)

            await ws.send_json({
                "type": "done",
                "full_text": full_response,
                "tools_used": tools_used,
                "agent_id": agent_id,
                "agent_name": agent.name,
            })

        except Exception as e:
            logger.error(f"Agent '{agent_id}' chat error: {e}")
            await ws.send_json({"type": "error", "message": str(e)})

    def _resolve_image_paths(self, image_ids: list) -> list[str]:
        """Resolve image IDs to file paths."""
        from pathlib import Path
        paths = []
        for img_id in image_ids:
            if img_id.startswith("/api/uploads/"):
                img_id = img_id.split("/")[-1]
            file_path = Path("data/uploads") / img_id
            if file_path.exists():
                paths.append(str(file_path))
        return paths

    async def broadcast(self, agent_id: str, message: dict):
        """Send a message to all connections for an agent."""
        connections = self.connections.get(agent_id, [])
        for ws in connections:
            if not ws.closed:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

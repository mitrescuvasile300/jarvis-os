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
    """Manages WebSocket connections for agent chat."""

    def __init__(self, agent):
        self.agent = agent
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
        """Handle a chat message with streaming response."""
        text = data.get("text", "").strip()
        if not text:
            await ws.send_json({"type": "error", "message": "Empty message"})
            return

        conversation_id = data.get("conversation_id", f"ws_{agent_id}")

        # Acknowledge receipt
        await ws.send_json({"type": "thinking", "text": "Processing..."})

        try:
            # Try streaming response
            tools_used = []
            full_response = ""

            if hasattr(self.agent, "chat_stream"):
                # Streaming mode — token by token
                async for chunk in self.agent.chat_stream(text, conversation_id=conversation_id):
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
                # Fallback: non-streaming (simulate streaming by sending word by word)
                response = await self.agent.chat(text, conversation_id=conversation_id)
                full_response = response.get("text", "")
                tools_used = response.get("tools_used", [])

                # Simulate streaming for smooth UX
                words = full_response.split(" ")
                for i, word in enumerate(words):
                    token = word + (" " if i < len(words) - 1 else "")
                    await ws.send_json({"type": "token", "text": token})
                    await asyncio.sleep(0.02)  # 20ms per word

            # Done
            await ws.send_json({
                "type": "done",
                "full_text": full_response,
                "tools_used": tools_used,
            })

        except Exception as e:
            logger.error(f"Chat error: {e}")
            await ws.send_json({"type": "error", "message": str(e)})

    async def broadcast(self, agent_id: str, message: dict):
        """Send a message to all connections for an agent."""
        connections = self.connections.get(agent_id, [])
        for ws in connections:
            if not ws.closed:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

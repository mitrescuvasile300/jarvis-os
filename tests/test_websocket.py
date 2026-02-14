"""Tests for WebSocket handler."""

import json
import pytest

from jarvis.websocket_handler import ChatWebSocket


class TestChatWebSocket:
    """Test the WebSocket handler initialization."""

    def test_creates_with_agent(self):
        class MockAgent:
            name = "TestAgent"
        ws_handler = ChatWebSocket(MockAgent())
        assert ws_handler.agent.name == "TestAgent"
        assert ws_handler.connections == {}

    def test_connection_tracking_dict(self):
        class MockAgent:
            name = "TestAgent"
        ws_handler = ChatWebSocket(MockAgent())
        # Should be empty by default
        assert len(ws_handler.connections) == 0

    def test_broadcast_no_connections(self):
        """Broadcast with no connections should not raise."""
        import asyncio

        class MockAgent:
            name = "TestAgent"
        ws_handler = ChatWebSocket(MockAgent())

        # Should not raise
        asyncio.get_event_loop().run_until_complete(
            ws_handler.broadcast("nonexistent", {"type": "test"})
        )

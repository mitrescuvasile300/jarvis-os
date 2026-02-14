"""Tests for the HTTP server setup."""

import pytest

from jarvis.server import JarvisServer


class TestServerCreation:
    """Test server initialization."""

    def test_creates_app(self):
        server = JarvisServer()
        app = server.create_app()
        assert app is not None

    def test_app_has_routes(self):
        server = JarvisServer()
        app = server.create_app()
        routes = [r.resource.canonical for r in app.router.routes() if hasattr(r, 'resource') and r.resource]
        # Check key routes exist
        assert "/" in routes
        assert "/health" in routes
        assert "/api/chat" in routes
        assert "/ws/chat" in routes
        assert "/api/plugins" in routes

    def test_config_loaded(self):
        server = JarvisServer()
        assert server.config is not None
        assert "agent" in server.config
        assert "server" in server.config

    def test_ws_handler_created(self):
        server = JarvisServer()
        assert server.ws_handler is not None

    def test_plugin_loader_created(self):
        server = JarvisServer()
        assert server.plugin_loader is not None

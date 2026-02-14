"""Tests for the Jarvis agent core."""

import pytest
from jarvis.config import load_config


class TestAgentConfig:
    def test_default_config_valid(self):
        config = load_config("config")
        assert "agent" in config
        assert "memory" in config
        assert "server" in config
        assert config["agent"]["name"] == "Jarvis"

    def test_skills_in_config(self):
        config = load_config("config")
        assert "skills" in config
        enabled = config["skills"].get("enabled", [])
        assert "trading" in enabled
        assert "research" in enabled
        assert "content" in enabled
        assert "code" in enabled

"""Tests for configuration loading."""

import os
import pytest
from jarvis.config import load_config, _deep_merge, _apply_env_overrides


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"agent": {"name": "Jarvis", "llm": {"provider": "openai"}}}
        override = {"agent": {"llm": {"model": "gpt-4o"}}}
        result = _deep_merge(base, override)
        assert result["agent"]["name"] == "Jarvis"
        assert result["agent"]["llm"]["provider"] == "openai"
        assert result["agent"]["llm"]["model"] == "gpt-4o"

    def test_override_preserves_original(self):
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        result = _deep_merge(base, override)
        assert result["a"]["b"] == 2
        # Original not modified
        assert base["a"]["b"] == 1


class TestConfigLoader:
    def test_defaults_loaded(self):
        config = load_config("nonexistent_dir")
        assert config["agent"]["name"] == "Jarvis"
        assert config["agent"]["llm"]["provider"] == "openai"
        assert config["memory"]["backend"] == "sqlite"
        assert config["server"]["port"] == 8080

    def test_env_override(self):
        os.environ["AGENT_NAME"] = "TestBot"
        os.environ["LLM_PROVIDER"] = "anthropic"
        try:
            config = load_config("nonexistent_dir")
            assert config["agent"]["name"] == "TestBot"
            assert config["agent"]["llm"]["provider"] == "anthropic"
        finally:
            del os.environ["AGENT_NAME"]
            del os.environ["LLM_PROVIDER"]

    def test_port_env_is_int(self):
        os.environ["AGENT_PORT"] = "9090"
        try:
            config = load_config("nonexistent_dir")
            assert config["server"]["port"] == 9090
            assert isinstance(config["server"]["port"], int)
        finally:
            del os.environ["AGENT_PORT"]

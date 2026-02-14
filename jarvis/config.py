"""Configuration loader for Jarvis OS.

Reads from config/*.yml files and merges with environment variables.
Environment variables always take precedence.
"""

import os
from pathlib import Path

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml(path: str | Path) -> dict:
    """Load a YAML file, return empty dict if not found."""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _apply_env_overrides(config: dict) -> dict:
    """Override config values with environment variables."""
    env_map = {
        "LLM_PROVIDER": ("agent", "llm", "provider"),
        "OPENAI_API_KEY": ("agent", "llm", "openai_api_key"),
        "OPENAI_MODEL": ("agent", "llm", "model"),
        "ANTHROPIC_API_KEY": ("agent", "llm", "anthropic_api_key"),
        "ANTHROPIC_MODEL": ("agent", "llm", "model"),
        "OLLAMA_HOST": ("agent", "llm", "ollama_host"),
        "OLLAMA_MODEL": ("agent", "llm", "model"),
        "AGENT_NAME": ("agent", "name"),
        "SERVER_PORT": ("server", "port"),
        "AGENT_API_KEY": ("agent", "api_key"),
        "AGENT_LOG_LEVEL": ("agent", "log_level"),
        "MEMORY_BACKEND": ("memory", "backend"),
        "VECTOR_STORE": ("memory", "vector_store"),
        "DATABASE_URL": ("memory", "database_url"),
        "MEMORY_RETENTION_DAYS": ("memory", "retention_days"),
        "SLACK_BOT_TOKEN": ("integrations", "slack", "bot_token"),
        "SLACK_APP_TOKEN": ("integrations", "slack", "app_token"),
        "SLACK_SIGNING_SECRET": ("integrations", "slack", "signing_secret"),
        "TWITTER_API_KEY": ("integrations", "twitter", "api_key"),
        "TWITTER_API_SECRET": ("integrations", "twitter", "api_secret"),
        "TWITTER_ACCESS_TOKEN": ("integrations", "twitter", "access_token"),
        "TWITTER_ACCESS_SECRET": ("integrations", "twitter", "access_secret"),
        "GITHUB_TOKEN": ("integrations", "github", "token"),
    }

    for env_var, path in env_map.items():
        value = os.getenv(env_var)
        if value is not None:
            # Navigate to the nested key and set it
            current = config
            for key in path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            # Convert port to int
            if env_var == "SERVER_PORT":
                value = int(value)
            elif env_var == "MEMORY_RETENTION_DAYS":
                value = int(value)
            current[path[-1]] = value

    return config


def load_config(config_dir: str = "config") -> dict:
    """Load full configuration from YAML files + environment.

    Precedence (highest to lowest):
    1. Environment variables
    2. config/jarvis.yml
    3. config/integrations.yml
    4. Defaults
    """
    defaults = {
        "agent": {
            "name": "Jarvis",
            "llm": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "log_level": "INFO",
        },
        "memory": {
            "backend": "sqlite",
            "vector_store": "chromadb",
            "retention_days": 365,
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8080,
        },
        "skills": {
            "enabled": [],
        },
        "integrations": {},
    }

    config_path = Path(config_dir)

    # Load YAML configs
    jarvis_config = _load_yaml(config_path / "jarvis.yml")
    integrations_config = _load_yaml(config_path / "integrations.yml")
    crons_config = _load_yaml(config_path / "crons.yml")

    # Merge: defaults ← jarvis.yml ← integrations
    config = _deep_merge(defaults, jarvis_config)
    if integrations_config:
        config = _deep_merge(config, {"integrations": integrations_config})
    if crons_config:
        config["crons"] = crons_config

    # Apply environment overrides (highest priority)
    config = _apply_env_overrides(config)

    return config

"""Tests for jarvis init command and templates."""

import json
import pytest
from pathlib import Path

from jarvis.init_command import create_agent_workspace, list_templates, TEMPLATES


class TestListTemplates:
    def test_all_templates_present(self):
        templates = list_templates()
        expected = ["trading", "research", "content", "social-media", "support", "devops", "personal-assistant", "custom"]
        for t in expected:
            assert t in templates, f"Template '{t}' missing"

    def test_8_templates_total(self):
        assert len(TEMPLATES) == 8


class TestCreateWorkspace:
    def test_creates_directory(self, tmp_path):
        path = create_agent_workspace("test-bot", "trading", str(tmp_path))
        assert Path(path).exists()
        assert Path(path).is_dir()

    def test_creates_agent_config(self, tmp_path):
        path = create_agent_workspace("test-bot", "trading", str(tmp_path))
        config_file = Path(path) / "agent.config.json"
        assert config_file.exists()

        config = json.loads(config_file.read_text())
        assert config["name"] == "test-bot"
        assert config["template"] == "trading"
        assert config["model"] == "gpt-4o"
        assert "safety" in config

    def test_trading_has_checklist(self, tmp_path):
        path = create_agent_workspace("test-bot", "trading", str(tmp_path))
        config = json.loads((Path(path) / "agent.config.json").read_text())
        assert "skill_config" in config
        assert "trading" in config["skill_config"]
        checklist = config["skill_config"]["trading"]["checklist"]
        assert len(checklist["criteria"]) == 10
        assert checklist["min_score"] == 8

    def test_creates_env_file(self, tmp_path):
        path = create_agent_workspace("test-bot", "custom", str(tmp_path))
        env_file = Path(path) / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "OPENAI_API_KEY" in content

    def test_creates_skill_md(self, tmp_path):
        path = create_agent_workspace("test-bot", "research", str(tmp_path))
        skill_md = Path(path) / "skills" / "SKILL.md"
        assert skill_md.exists()

    def test_creates_subdirectories(self, tmp_path):
        path = create_agent_workspace("test-bot", "custom", str(tmp_path))
        assert (Path(path) / "skills").is_dir()
        assert (Path(path) / "scripts").is_dir()
        assert (Path(path) / "logs").is_dir()
        assert (Path(path) / "data").is_dir()

    def test_invalid_template_raises(self, tmp_path):
        with pytest.raises(ValueError):
            create_agent_workspace("test", "nonexistent", str(tmp_path))

    def test_all_templates_create_successfully(self, tmp_path):
        for template_name in TEMPLATES:
            path = create_agent_workspace(f"agent-{template_name}", template_name, str(tmp_path))
            assert Path(path).exists()
            assert (Path(path) / "agent.config.json").exists()


class TestTradingTemplate:
    def test_safety_config(self, tmp_path):
        path = create_agent_workspace("trader", "trading", str(tmp_path))
        config = json.loads((Path(path) / "agent.config.json").read_text())
        assert config["safety"]["kill_switch"] is True
        assert config["safety"]["max_spend_per_trade"] == 0.5

    def test_trading_tools(self, tmp_path):
        path = create_agent_workspace("trader", "trading", str(tmp_path))
        config = json.loads((Path(path) / "agent.config.json").read_text())
        assert "http_request" in config["tools"]
        assert "web_search" in config["tools"]
        assert "run_code" in config["tools"]

"""Tests for AgentManager — agent spawning, communication, persistence."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# Minimal mock LLM client
class MockLLM:
    async def chat(self, messages=None, tools=None, temperature=0.7, max_tokens=4096):
        return {"text": "I am a test agent response."}


# Minimal mock tool registry
class MockToolRegistry:
    def get_definitions(self):
        return [
            {"name": "web_search", "description": "Search the web", "parameters": {}},
            {"name": "browse", "description": "Browse a URL", "parameters": {}},
        ]

    async def execute(self, name, arguments):
        return f"Mock result for {name}"

    def list(self):
        return ["web_search", "browse"]

    def register(self, **kwargs):
        pass


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create temp data directory for agent persistence."""
    agents_dir = tmp_path / "data" / "agents"
    agents_dir.mkdir(parents=True)
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)


@pytest.fixture
def agent_manager(tmp_data_dir):
    from jarvis.agent_manager import AgentManager
    llm = MockLLM()
    tools = MockToolRegistry()
    config = {"agent": {"llm": {"model": "test-model"}}}
    return AgentManager(llm, tools, config)


class TestAgentCreation:
    @pytest.mark.asyncio
    async def test_create_agent(self, agent_manager):
        agent = await agent_manager.create_agent(
            name="Research Bot", template="research"
        )
        assert agent.name == "Research Bot"
        assert agent.template == "research"
        assert agent.id.startswith("agent_")
        assert agent.status == "idle"

    @pytest.mark.asyncio
    async def test_create_agent_with_personality(self, agent_manager):
        agent = await agent_manager.create_agent(
            name="Custom Bot", template="custom", personality="Be very formal"
        )
        assert agent.personality == "Be very formal"

    @pytest.mark.asyncio
    async def test_agent_persisted_to_disk(self, agent_manager, tmp_data_dir):
        agent = await agent_manager.create_agent(name="Persist Bot", template="trading")
        agent_file = tmp_data_dir / "data" / "agents" / f"{agent.id}.json"
        assert agent_file.exists()
        data = json.loads(agent_file.read_text())
        assert data["name"] == "Persist Bot"
        assert data["template"] == "trading"

    @pytest.mark.asyncio
    async def test_list_agents(self, agent_manager):
        await agent_manager.create_agent(name="A1", template="research")
        await agent_manager.create_agent(name="A2", template="trading")
        agents = agent_manager.list_agents()
        assert len(agents) == 2
        names = {a["name"] for a in agents}
        assert names == {"A1", "A2"}

    @pytest.mark.asyncio
    async def test_get_agent(self, agent_manager):
        agent = await agent_manager.create_agent(name="Findable", template="custom")
        found = agent_manager.get_agent(agent.id)
        assert found is not None
        assert found.name == "Findable"

    @pytest.mark.asyncio
    async def test_get_missing_agent(self, agent_manager):
        assert agent_manager.get_agent("agent_nonexistent") is None


class TestAgentDeletion:
    @pytest.mark.asyncio
    async def test_delete_agent(self, agent_manager, tmp_data_dir):
        agent = await agent_manager.create_agent(name="Delete Me", template="custom")
        agent_id = agent.id
        deleted = await agent_manager.delete_agent(agent_id)
        assert deleted is True
        assert agent_manager.get_agent(agent_id) is None
        agent_file = tmp_data_dir / "data" / "agents" / f"{agent_id}.json"
        assert not agent_file.exists()

    @pytest.mark.asyncio
    async def test_delete_missing_agent(self, agent_manager):
        deleted = await agent_manager.delete_agent("agent_fake")
        assert deleted is False


class TestAgentChat:
    @pytest.mark.asyncio
    async def test_chat_returns_text(self, agent_manager):
        agent = await agent_manager.create_agent(name="Chatty", template="research")
        result = await agent_manager.chat_with_agent(agent.id, "Hello!")
        assert "text" in result
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_chat_stores_conversation(self, agent_manager):
        agent = await agent_manager.create_agent(name="Memory", template="custom")
        await agent_manager.chat_with_agent(agent.id, "Remember this")
        assert len(agent.conversation) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_chat_missing_agent(self, agent_manager):
        result = await agent_manager.chat_with_agent("agent_none", "Hello")
        assert "error" in result or result.get("text") == "Agent not found."

    @pytest.mark.asyncio
    async def test_agent_status_during_chat(self, agent_manager):
        agent = await agent_manager.create_agent(name="Busy", template="custom")
        # After chat, status should be idle
        await agent_manager.chat_with_agent(agent.id, "Test")
        assert agent.status == "idle"


class TestAgentTasks:
    @pytest.mark.asyncio
    async def test_send_task(self, agent_manager):
        agent = await agent_manager.create_agent(name="Worker", template="research")
        result = await agent_manager.send_task(agent.id, "Research AI news")
        assert "text" in result
        assert "task_id" in result

    @pytest.mark.asyncio
    async def test_send_task_missing_agent(self, agent_manager):
        result = await agent_manager.send_task("agent_fake", "Do something")
        assert "error" in result


class TestAgentPersistence:
    @pytest.mark.asyncio
    async def test_load_persisted_agents(self, tmp_data_dir):
        from jarvis.agent_manager import AgentManager

        llm = MockLLM()
        tools = MockToolRegistry()
        config = {"agent": {"llm": {"model": "test"}}}

        # Create first manager, add agent
        mgr1 = AgentManager(llm, tools, config)
        agent = await mgr1.create_agent(name="Persistent", template="research")
        agent_id = agent.id
        await mgr1.chat_with_agent(agent_id, "Remember me")

        # Create second manager, load from disk
        mgr2 = AgentManager(llm, tools, config)
        mgr2.load_persisted_agents()
        assert len(mgr2.agents) == 1
        loaded = mgr2.get_agent(agent_id)
        assert loaded is not None
        assert loaded.name == "Persistent"


class TestAgentTemplates:
    def test_all_templates_exist(self, agent_manager):
        templates = agent_manager.get_templates()
        assert "research" in templates
        assert "trading" in templates
        assert "content" in templates
        assert "devops" in templates
        assert "custom" in templates

    @pytest.mark.asyncio
    async def test_research_has_correct_tools(self, agent_manager):
        agent = await agent_manager.create_agent(name="R", template="research")
        assert "web_search" in agent.allowed_tools
        assert "browse" in agent.allowed_tools

    @pytest.mark.asyncio
    async def test_custom_has_all_tools(self, agent_manager):
        agent = await agent_manager.create_agent(name="C", template="custom")
        assert agent.allowed_tools is None  # None = all tools


class TestAgentToolFiltering:
    @pytest.mark.asyncio
    async def test_tool_definitions_filtered(self, agent_manager):
        agent = await agent_manager.create_agent(
            name="Limited", template="custom", tools=["web_search"]
        )
        defs = agent.get_tool_definitions()
        assert len(defs) == 1
        assert defs[0]["name"] == "web_search"

    @pytest.mark.asyncio
    async def test_all_tools_when_none(self, agent_manager):
        agent = await agent_manager.create_agent(name="Full", template="custom")
        defs = agent.get_tool_definitions()
        assert len(defs) == 2  # All mock tools


class TestAgentSerialization:
    @pytest.mark.asyncio
    async def test_to_dict(self, agent_manager):
        agent = await agent_manager.create_agent(
            name="Serial", template="research", personality="Friendly"
        )
        d = agent.to_dict()
        assert d["name"] == "Serial"
        assert d["template"] == "research"
        assert d["status"] == "idle"
        assert d["personality"] == "Friendly"
        assert "id" in d
        assert "created_at" in d

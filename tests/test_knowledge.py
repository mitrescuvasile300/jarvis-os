"""Tests for the Knowledge Manager."""

import json
import pytest
import pytest_asyncio
from pathlib import Path
import tempfile
import shutil

from jarvis.knowledge_manager import KnowledgeManager, DEFAULT_FILES


@pytest_asyncio.fixture
async def knowledge(tmp_path):
    """Create a test knowledge manager with temp directory."""
    km = KnowledgeManager(config={}, knowledge_dir=str(tmp_path / "knowledge"))
    await km.initialize()
    yield km


class TestInitialization:
    @pytest.mark.asyncio
    async def test_creates_directory(self, tmp_path):
        km = KnowledgeManager(config={}, knowledge_dir=str(tmp_path / "test_knowledge"))
        await km.initialize()
        assert (tmp_path / "test_knowledge").exists()

    @pytest.mark.asyncio
    async def test_creates_default_files(self, knowledge, tmp_path):
        knowledge_dir = tmp_path / "knowledge"
        for filename in DEFAULT_FILES:
            assert (knowledge_dir / filename).exists()

    @pytest.mark.asyncio
    async def test_loads_into_cache(self, knowledge):
        all_knowledge = knowledge.get_all_knowledge()
        assert len(all_knowledge) == len(DEFAULT_FILES)
        assert "user-profile.md" in all_knowledge
        assert "context.md" in all_knowledge

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing(self, tmp_path):
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "user-profile.md").write_text("# Custom Profile\nMy data")

        km = KnowledgeManager(config={}, knowledge_dir=str(knowledge_dir))
        await km.initialize()

        content = km.get_user_profile()
        assert "Custom Profile" in content
        assert "My data" in content


class TestRecall:
    @pytest.mark.asyncio
    async def test_always_includes_core_files(self, knowledge):
        result = await knowledge.recall("hello")
        assert "user-profile.md" in result
        assert "context.md" in result

    @pytest.mark.asyncio
    async def test_includes_learnings_on_error_message(self, knowledge):
        result = await knowledge.recall("I have an error with the server")
        assert "learnings.md" in result

    @pytest.mark.asyncio
    async def test_includes_decisions_on_decision_message(self, knowledge):
        result = await knowledge.recall("should we use PostgreSQL or SQLite?")
        assert "decisions.md" in result

    @pytest.mark.asyncio
    async def test_custom_files_match_by_topic(self, knowledge, tmp_path):
        # Create a custom knowledge file
        custom_file = tmp_path / "knowledge" / "trading.md"
        custom_file.write_text("# Trading Knowledge\nBuy low sell high")
        await knowledge._load_all()

        result = await knowledge.recall("what about trading today?")
        assert "trading.md" in result


class TestLearnParsing:
    def test_parse_valid_json(self, knowledge):
        text = '{"user-profile.md": ["Likes dark mode"]}'
        result = knowledge._parse_learning_output(text)
        assert "user-profile.md" in result
        assert result["user-profile.md"] == ["Likes dark mode"]

    def test_parse_json_in_code_block(self, knowledge):
        text = '```json\n{"context.md": ["Working on Jarvis"]}\n```'
        result = knowledge._parse_learning_output(text)
        assert "context.md" in result

    def test_parse_empty_json(self, knowledge):
        result = knowledge._parse_learning_output("{}")
        assert result == {}

    def test_parse_invalid_text(self, knowledge):
        result = knowledge._parse_learning_output("Nothing to remember")
        assert result == {}

    def test_parse_json_with_surrounding_text(self, knowledge):
        text = 'Here is the extraction:\n{"learnings.md": ["SQLite is faster"]}\nDone.'
        result = knowledge._parse_learning_output(text)
        assert "learnings.md" in result


class TestAppendToFile:
    @pytest.mark.asyncio
    async def test_append_entries(self, knowledge, tmp_path):
        await knowledge._append_to_file("user-profile.md", ["Prefers dark mode"])
        content = (tmp_path / "knowledge" / "user-profile.md").read_text()
        assert "Prefers dark mode" in content

    @pytest.mark.asyncio
    async def test_removes_placeholder(self, knowledge, tmp_path):
        await knowledge._append_to_file("user-profile.md", ["Some preference"])
        content = (tmp_path / "knowledge" / "user-profile.md").read_text()
        assert "(none yet)" not in content

    @pytest.mark.asyncio
    async def test_adds_timestamp(self, knowledge, tmp_path):
        await knowledge._append_to_file("context.md", ["Working on tests"])
        content = (tmp_path / "knowledge" / "context.md").read_text()
        # Should have a timestamp like [2026-02-14 23:50]
        assert "- [20" in content

    @pytest.mark.asyncio
    async def test_creates_new_file(self, knowledge, tmp_path):
        await knowledge._append_to_file("custom-topic.md", ["Some fact"])
        assert (tmp_path / "knowledge" / "custom-topic.md").exists()

    @pytest.mark.asyncio
    async def test_updates_cache(self, knowledge):
        await knowledge._append_to_file("learnings.md", ["New learning"])
        cached = knowledge._cache.get("learnings.md", "")
        assert "New learning" in cached


class TestFormatForPrompt:
    def test_format_basic(self, knowledge):
        data = {"user-profile.md": "# User Profile\n\n## Preferences\n- Dark mode\n"}
        result = knowledge.format_for_prompt(data)
        assert "user-profile.md" in result
        assert "Dark mode" in result

    def test_skips_empty_files(self, knowledge):
        data = {
            "user-profile.md": "# User Profile\n\n## Preferences\n(none yet)\n\n## Communication Style\n(none yet)\n\n## Important Info\n(none yet)\n"
        }
        result = knowledge.format_for_prompt(data)
        # File is mostly empty, should be skipped
        assert "user-profile.md" not in result

    def test_empty_knowledge(self, knowledge):
        result = knowledge.format_for_prompt({})
        assert result == ""


class TestStats:
    @pytest.mark.asyncio
    async def test_stats_structure(self, knowledge):
        stats = await knowledge.get_stats()
        assert "total_files" in stats
        assert "total_entries" in stats
        assert "total_chars" in stats
        assert "files" in stats
        assert stats["total_files"] == len(DEFAULT_FILES)

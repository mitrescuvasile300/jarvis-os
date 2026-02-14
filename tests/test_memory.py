"""Tests for the memory store."""

import pytest
import pytest_asyncio
from jarvis.memory_store import MemoryStore


@pytest_asyncio.fixture
async def memory():
    """Create a test memory store."""
    store = MemoryStore({
        "backend": "sqlite",
        "vector_store": "none",  # Skip ChromaDB in tests
        "retention_days": 30,
    })
    # Use in-memory SQLite for tests
    import sqlite3
    store.db_path = ":memory:"
    store.db = sqlite3.connect(":memory:")
    store.db.row_factory = sqlite3.Row
    store._create_tables()
    yield store
    await store.close()


class TestConversationMemory:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, memory):
        await memory.store_message("conv1", "user", "Hello!")
        await memory.store_message("conv1", "assistant", "Hi there!")

        messages = await memory.get_conversation("conv1")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"
        assert messages[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_separate_conversations(self, memory):
        await memory.store_message("conv1", "user", "Message 1")
        await memory.store_message("conv2", "user", "Message 2")

        conv1 = await memory.get_conversation("conv1")
        conv2 = await memory.get_conversation("conv2")
        assert len(conv1) == 1
        assert len(conv2) == 1
        assert conv1[0]["content"] == "Message 1"
        assert conv2[0]["content"] == "Message 2"

    @pytest.mark.asyncio
    async def test_limit(self, memory):
        for i in range(30):
            await memory.store_message("conv", "user", f"Message {i}")

        messages = await memory.get_conversation("conv", limit=5)
        assert len(messages) == 5


class TestKnowledgeMemory:
    @pytest.mark.asyncio
    async def test_store_knowledge(self, memory):
        await memory.store_knowledge("Python is a programming language", category="tech")
        count = await memory.count()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_search_knowledge(self, memory):
        await memory.store_knowledge("The user prefers dark mode")
        await memory.store_knowledge("Meeting scheduled for Monday")

        results = await memory.search("dark mode")
        assert len(results) >= 1
        assert "dark mode" in results[0]["content"]


class TestWorkingMemory:
    @pytest.mark.asyncio
    async def test_set_and_get(self, memory):
        await memory.set_working("task_status", {"step": 2, "total": 5}, task_id="task1")
        value = await memory.get_working("task_status")
        assert value == {"step": 2, "total": 5}

    @pytest.mark.asyncio
    async def test_missing_key(self, memory):
        value = await memory.get_working("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_overwrite(self, memory):
        await memory.set_working("key", "value1")
        await memory.set_working("key", "value2")
        value = await memory.get_working("key")
        assert value == "value2"


class TestCount:
    @pytest.mark.asyncio
    async def test_empty_count(self, memory):
        count = await memory.count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_after_inserts(self, memory):
        await memory.store_message("conv", "user", "Hello")
        await memory.store_knowledge("Some fact")
        count = await memory.count()
        assert count == 2

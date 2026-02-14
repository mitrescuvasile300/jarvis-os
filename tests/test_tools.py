"""Tests for tool registry and built-in tools."""

import os
import pytest
from pathlib import Path
from jarvis.tools import ToolRegistry, tool_read_file, tool_write_file, tool_list_files


class TestToolRegistry:
    def test_register_and_list(self):
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object"},
            handler=lambda args: "ok",
        )
        assert "test_tool" in registry.list()

    def test_get_definitions(self):
        registry = ToolRegistry()
        registry.register_defaults()
        definitions = registry.get_definitions()
        assert len(definitions) > 0
        assert all("name" in d for d in definitions)
        assert all("description" in d for d in definitions)
        assert all("parameters" in d for d in definitions)

    def test_default_tools_registered(self):
        registry = ToolRegistry()
        registry.register_defaults()
        tools = registry.list()
        assert "web_search" in tools
        assert "read_file" in tools
        assert "write_file" in tools
        assert "run_code" in tools
        assert "shell_command" in tools
        assert "http_request" in tools
        assert "list_files" in tools
        assert "search_files" in tools

    @pytest.mark.asyncio
    async def test_execute_missing_tool(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            await registry.execute("nonexistent", {})


class TestFileTools:
    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        result = await tool_read_file({"path": str(test_file)})
        assert result == "Hello World"

    @pytest.mark.asyncio
    async def test_read_missing_file(self):
        result = await tool_read_file({"path": "/nonexistent/file.txt"})
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_write_file(self, tmp_path):
        test_file = tmp_path / "output.txt"
        result = await tool_write_file({"path": str(test_file), "content": "Test content"})
        assert "Written" in result
        assert test_file.read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_write_creates_dirs(self, tmp_path):
        test_file = tmp_path / "sub" / "dir" / "file.txt"
        await tool_write_file({"path": str(test_file), "content": "Nested"})
        assert test_file.read_text() == "Nested"

    @pytest.mark.asyncio
    async def test_list_files(self, tmp_path):
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.txt").write_text("c")

        result = await tool_list_files({"path": str(tmp_path)})
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" in result

    @pytest.mark.asyncio
    async def test_list_files_with_pattern(self, tmp_path):
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        result = await tool_list_files({"path": str(tmp_path), "pattern": "*.py"})
        assert "a.py" in result
        assert "b.txt" not in result

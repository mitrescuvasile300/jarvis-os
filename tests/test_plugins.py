"""Tests for the plugin system."""

import asyncio
import os
import tempfile

import pytest

from jarvis.plugins import PluginLoader, plugin_tool, _plugin_registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear plugin registry between tests."""
    _plugin_registry.clear()
    yield
    _plugin_registry.clear()


class TestPluginDecorator:
    """Test the @plugin_tool decorator."""

    def test_registers_sync_function(self):
        @plugin_tool(name="test_sync", description="A sync tool", parameters={"x": "input"})
        def my_sync(x: str) -> str:
            return x

        assert "test_sync" in _plugin_registry
        assert _plugin_registry["test_sync"]["description"] == "A sync tool"
        assert _plugin_registry["test_sync"]["is_async"] is False

    def test_registers_async_function(self):
        @plugin_tool(name="test_async", description="An async tool", parameters={})
        async def my_async() -> str:
            return "ok"

        assert "test_async" in _plugin_registry
        assert _plugin_registry["test_async"]["is_async"] is True

    def test_parameters_stored(self):
        @plugin_tool(name="param_test", description="Test", parameters={"a": "desc a", "b": "desc b"})
        def fn(a: str, b: str) -> str:
            return a + b

        assert _plugin_registry["param_test"]["parameters"] == {"a": "desc a", "b": "desc b"}

    def test_empty_parameters(self):
        @plugin_tool(name="no_params", description="No params")
        def fn() -> str:
            return "ok"

        assert _plugin_registry["no_params"]["parameters"] == {}


class TestPluginLoader:
    """Test discovering and loading plugin files."""

    def test_discover_empty_dir(self, tmp_path):
        loader = PluginLoader(str(tmp_path))
        assert loader.discover() == []

    def test_discover_finds_py_files(self, tmp_path):
        (tmp_path / "tool_a.py").write_text("# plugin a")
        (tmp_path / "tool_b.py").write_text("# plugin b")
        (tmp_path / "_private.py").write_text("# skip")
        (tmp_path / "readme.md").write_text("# not a plugin")

        loader = PluginLoader(str(tmp_path))
        found = loader.discover()
        assert len(found) == 2
        assert any("tool_a.py" in f for f in found)

    def test_discover_nonexistent_dir(self):
        loader = PluginLoader("/nonexistent/path")
        assert loader.discover() == []

    def test_load_plugin_file(self, tmp_path):
        plugin_code = '''
from jarvis.plugins import plugin_tool

@plugin_tool(name="loaded_tool", description="Test loaded tool", parameters={"msg": "input"})
def loaded_tool(msg: str) -> str:
    return f"echo: {msg}"
'''
        (tmp_path / "my_plugin.py").write_text(plugin_code)

        loader = PluginLoader(str(tmp_path))
        tools = loader.load_all()

        assert "loaded_tool" in tools
        assert tools["loaded_tool"]["description"] == "Test loaded tool"

    def test_execute_sync_tool(self, tmp_path):
        plugin_code = '''
from jarvis.plugins import plugin_tool

@plugin_tool(name="sync_exec", description="Sync", parameters={"val": "value"})
def sync_exec(val: str) -> str:
    return f"got: {val}"
'''
        (tmp_path / "sync.py").write_text(plugin_code)
        loader = PluginLoader(str(tmp_path))
        loader.load_all()

        result = asyncio.get_event_loop().run_until_complete(
            loader.execute_tool("sync_exec", val="hello")
        )
        assert result == "got: hello"

    def test_execute_async_tool(self, tmp_path):
        plugin_code = '''
from jarvis.plugins import plugin_tool

@plugin_tool(name="async_exec", description="Async", parameters={"val": "value"})
async def async_exec(val: str) -> str:
    return f"async: {val}"
'''
        (tmp_path / "async_plugin.py").write_text(plugin_code)
        loader = PluginLoader(str(tmp_path))
        loader.load_all()

        result = asyncio.get_event_loop().run_until_complete(
            loader.execute_tool("async_exec", val="world")
        )
        assert result == "async: world"

    def test_execute_missing_tool(self, tmp_path):
        loader = PluginLoader(str(tmp_path))
        with pytest.raises(ValueError, match="not found"):
            asyncio.get_event_loop().run_until_complete(
                loader.execute_tool("nonexistent")
            )

    def test_get_tool_definitions(self, tmp_path):
        plugin_code = '''
from jarvis.plugins import plugin_tool

@plugin_tool(name="def_test", description="Def test", parameters={"query": "search query"})
def def_test(query: str) -> str:
    return query
'''
        (tmp_path / "def.py").write_text(plugin_code)
        loader = PluginLoader(str(tmp_path))
        loader.load_all()

        defs = loader.get_tool_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "def_test"
        assert "query" in defs[0]["function"]["parameters"]["properties"]

    def test_list_tools(self, tmp_path):
        plugin_code = '''
from jarvis.plugins import plugin_tool

@plugin_tool(name="list_a", description="A")
def a(): return "a"

@plugin_tool(name="list_b", description="B")
def b(): return "b"
'''
        (tmp_path / "multi.py").write_text(plugin_code)
        loader = PluginLoader(str(tmp_path))
        loader.load_all()

        tools = loader.list_tools()
        assert "list_a" in tools
        assert "list_b" in tools

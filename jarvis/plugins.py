"""Plugin system for custom tools and integrations.

Users can create plugins by adding Python files to the `plugins/` directory.
Each plugin is a Python file that registers tools using a simple decorator.

Example plugin (plugins/my_weather.py):

    from jarvis.plugins import plugin_tool

    @plugin_tool(
        name="get_weather",
        description="Get current weather for a city",
        parameters={"city": "Name of the city"}
    )
    async def get_weather(city: str) -> str:
        import httpx
        resp = await httpx.AsyncClient().get(
            f"https://wttr.in/{city}?format=3"
        )
        return resp.text
"""

import importlib.util
import inspect
import logging
import os
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("jarvis.plugins")

# Registry for plugin tools
_plugin_registry: dict[str, dict] = {}


def plugin_tool(
    name: str,
    description: str,
    parameters: dict[str, str] | None = None,
):
    """Decorator to register a function as a plugin tool.

    Args:
        name: Tool name (used in agent's tool calls)
        description: What the tool does (shown to the LLM)
        parameters: Dict of param_name -> description
    """
    def decorator(func: Callable):
        _plugin_registry[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {},
            "function": func,
            "is_async": inspect.iscoroutinefunction(func),
            "source": inspect.getfile(func),
        }
        logger.info(f"Registered plugin tool: {name}")
        return func
    return decorator


class PluginLoader:
    """Discovers and loads plugin files from a directory."""

    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.loaded_plugins: list[str] = []

    def discover(self) -> list[str]:
        """Find all plugin files."""
        if not self.plugin_dir.exists():
            return []

        plugins = []
        for path in self.plugin_dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            plugins.append(str(path))

        return plugins

    def load_all(self) -> dict[str, dict]:
        """Load all plugins and return registered tools."""
        plugin_files = self.discover()

        for filepath in plugin_files:
            try:
                self._load_file(filepath)
                self.loaded_plugins.append(filepath)
                logger.info(f"Loaded plugin: {filepath}")
            except Exception as e:
                logger.error(f"Failed to load plugin {filepath}: {e}")

        return dict(_plugin_registry)

    def _load_file(self, filepath: str):
        """Load a single plugin file."""
        path = Path(filepath)
        module_name = f"jarvis_plugin_{path.stem}"

        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {filepath}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    async def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a plugin tool by name."""
        if name not in _plugin_registry:
            raise ValueError(f"Plugin tool not found: {name}")

        tool = _plugin_registry[name]
        func = tool["function"]

        if tool["is_async"]:
            return await func(**kwargs)
        else:
            return func(**kwargs)

    def get_tool_definitions(self) -> list[dict]:
        """Get OpenAI-compatible tool definitions for all plugins."""
        definitions = []
        for name, tool in _plugin_registry.items():
            params = {}
            for param_name, param_desc in tool["parameters"].items():
                params[param_name] = {
                    "type": "string",
                    "description": param_desc,
                }

            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": params,
                        "required": list(tool["parameters"].keys()),
                    },
                },
            })
        return definitions

    def list_tools(self) -> list[str]:
        """List all registered plugin tool names."""
        return list(_plugin_registry.keys())

    def get_registry(self) -> dict[str, dict]:
        """Get the full plugin registry."""
        return dict(_plugin_registry)

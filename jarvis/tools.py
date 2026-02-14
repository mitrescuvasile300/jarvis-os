"""Tool Registry — built-in tools for the Jarvis agent.

Each tool is a callable that the LLM can invoke during conversations.
Tools have JSON schema definitions for the LLM and async execute functions.
"""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("jarvis.tools")


class ToolRegistry:
    """Registry of available tools for the agent."""

    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        """Register a tool."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler,
        }

    def register_defaults(self):
        """Register all built-in tools."""
        self.register(
            name="web_search",
            description="Search the web for information. Returns text results.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
            handler=tool_web_search,
        )

        self.register(
            name="read_file",
            description="Read the contents of a file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                },
                "required": ["path"],
            },
            handler=tool_read_file,
        )

        self.register(
            name="write_file",
            description="Write content to a file. Creates directories if needed.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
            handler=tool_write_file,
        )

        self.register(
            name="run_code",
            description="Execute Python code in a sandbox. Returns stdout/stderr.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                },
                "required": ["code"],
            },
            handler=tool_run_code,
        )

        self.register(
            name="shell_command",
            description="Execute a shell command. Returns stdout/stderr.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
            handler=tool_shell_command,
        )

        self.register(
            name="http_request",
            description="Make an HTTP request to an API.",
            parameters={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "description": "HTTP method"},
                    "url": {"type": "string", "description": "URL to request"},
                    "headers": {"type": "object", "description": "Request headers"},
                    "body": {"type": "string", "description": "Request body (for POST/PUT)"},
                },
                "required": ["method", "url"],
            },
            handler=tool_http_request,
        )

        self.register(
            name="list_files",
            description="List files in a directory.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                    "pattern": {"type": "string", "description": "Glob pattern (e.g., '*.py')"},
                },
                "required": ["path"],
            },
            handler=tool_list_files,
        )

        self.register(
            name="search_files",
            description="Search for a pattern in files (grep).",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex)"},
                    "path": {"type": "string", "description": "Directory to search in"},
                    "file_type": {"type": "string", "description": "File extension filter (e.g., 'py')"},
                },
                "required": ["pattern"],
            },
            handler=tool_search_files,
        )

    def get_definitions(self) -> list[dict]:
        """Get tool definitions for the LLM."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, arguments: dict) -> Any:
        """Execute a tool by name."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found")

        handler = self._tools[name]["handler"]
        return await handler(arguments)

    def list(self) -> list[str]:
        """List registered tool names."""
        return list(self._tools.keys())


# ── Tool Implementations ─────────────────────────────────────


async def tool_web_search(args: dict) -> str:
    """Search the web using DuckDuckGo (no API key needed)."""
    query = args["query"]
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return f"No results found for: {query}"
        output = []
        for r in results:
            output.append(f"**{r['title']}**\n{r['body']}\n{r['href']}\n")
        return "\n".join(output)
    except ImportError:
        return "Web search unavailable — install duckduckgo-search"
    except Exception as e:
        return f"Search error: {e}"


async def tool_read_file(args: dict) -> str:
    """Read a file's contents."""
    path = Path(args["path"])
    if not path.exists():
        return f"File not found: {path}"
    try:
        content = path.read_text(encoding="utf-8")
        if len(content) > 10000:
            return content[:10000] + f"\n\n... (truncated, {len(content)} total chars)"
        return content
    except Exception as e:
        return f"Error reading {path}: {e}"


async def tool_write_file(args: dict) -> str:
    """Write content to a file."""
    path = Path(args["path"])
    content = args["content"]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


async def tool_run_code(args: dict) -> str:
    """Execute Python code in a subprocess sandbox."""
    code = args["code"]
    timeout = int(os.getenv("CODE_EXEC_TIMEOUT", "30"))

    try:
        proc = await asyncio.create_subprocess_exec(
            "python", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            output += f"\nSTDERR: {stderr.decode('utf-8', errors='replace')}"
        if not output.strip():
            output = "(no output)"

        return output[:5000]
    except asyncio.TimeoutError:
        proc.kill()
        return f"Code execution timed out after {timeout}s"
    except Exception as e:
        return f"Execution error: {e}"


async def tool_shell_command(args: dict) -> str:
    """Execute a shell command."""
    command = args["command"]
    timeout = int(os.getenv("CODE_EXEC_TIMEOUT", "30"))

    # Safety check — block dangerous commands
    blocked = ["rm -rf /", "mkfs", "dd if=", ":(){:|:&};:", "chmod -R 777 /"]
    if any(b in command for b in blocked):
        return "Command blocked for safety reasons."

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            output += f"\nSTDERR: {stderr.decode('utf-8', errors='replace')}"
        if not output.strip():
            output = f"(exit code: {proc.returncode})"

        return output[:5000]
    except asyncio.TimeoutError:
        proc.kill()
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Shell error: {e}"


async def tool_http_request(args: dict) -> str:
    """Make an HTTP request."""
    try:
        import httpx
    except ImportError:
        return "httpx not installed — pip install httpx"

    method = args["method"].upper()
    url = args["url"]
    headers = args.get("headers", {})
    body = args.get("body")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=headers, content=body)

        result = f"HTTP {response.status_code}\n"
        content_type = response.headers.get("content-type", "")

        if "json" in content_type:
            try:
                data = response.json()
                result += json.dumps(data, indent=2)[:5000]
            except Exception:
                result += response.text[:5000]
        else:
            result += response.text[:5000]

        return result
    except Exception as e:
        return f"HTTP error: {e}"


async def tool_list_files(args: dict) -> str:
    """List files in a directory."""
    path = Path(args["path"])
    pattern = args.get("pattern", "*")

    if not path.exists():
        return f"Directory not found: {path}"

    try:
        files = sorted(path.glob(pattern))
        if not files:
            return f"No files matching '{pattern}' in {path}"

        output = []
        for f in files[:100]:
            size = f.stat().st_size if f.is_file() else 0
            icon = "📁" if f.is_dir() else "📄"
            output.append(f"{icon} {f.name} ({size:,} bytes)" if f.is_file() else f"{icon} {f.name}/")

        result = "\n".join(output)
        if len(files) > 100:
            result += f"\n... and {len(files) - 100} more"
        return result
    except Exception as e:
        return f"Error listing {path}: {e}"


async def tool_search_files(args: dict) -> str:
    """Search for a pattern in files."""
    pattern = args["pattern"]
    search_path = args.get("path", ".")
    file_type = args.get("file_type", "")

    cmd = f"grep -rn '{pattern}' {search_path}"
    if file_type:
        cmd += f" --include='*.{file_type}'"
    cmd += " | head -30"

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        output = stdout.decode("utf-8", errors="replace").strip()
        return output if output else f"No matches for '{pattern}'"
    except Exception as e:
        return f"Search error: {e}"

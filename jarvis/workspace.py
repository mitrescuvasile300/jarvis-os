"""Workspace — resolves all Jarvis data paths to the workspace directory.

The workspace is separate from the repo:
  ~/jarvis-os/           ← repo (code, git pull)
  ~/jarvis-workspace/    ← workspace (Jarvis's data, autonomous)

All components use workspace.path() to resolve paths:
  workspace.path("knowledge")          → ~/jarvis-workspace/knowledge/
  workspace.path("data/memory.db")     → ~/jarvis-workspace/data/memory.db
  workspace.path("projects/my-app")    → ~/jarvis-workspace/projects/my-app/

Configure via:
  - jarvis.yml:  workspace: "~/jarvis-workspace"
  - env var:     JARVIS_WORKSPACE=~/jarvis-workspace
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger("jarvis.workspace")

_workspace_root: Path | None = None

# Standard workspace subdirectories
WORKSPACE_DIRS = [
    "knowledge",     # user-profile.md, learnings.md, decisions.md, context.md
    "data",          # SQLite DB, ChromaDB vectors
    "data/agents",   # Sub-agent configs + conversations
    "data/chroma",   # Vector store
    "settings",      # keys.env (API keys from UI)
    "uploads",       # Images, files uploaded via chat
    "projects",      # Projects created by Jarvis
    "research",      # Research output, notes, articles
    "scripts",       # Scripts created by Jarvis
    "logs",          # Log files
]


def init(config: dict) -> Path:
    """Initialize the workspace from config or env var. Call once at startup."""
    global _workspace_root

    # Priority: env var > config > default
    ws_path = os.environ.get("JARVIS_WORKSPACE") or config.get("workspace", "~/jarvis-workspace")

    _workspace_root = Path(ws_path).expanduser().resolve()

    # Create all standard directories
    for subdir in WORKSPACE_DIRS:
        (_workspace_root / subdir).mkdir(parents=True, exist_ok=True)

    logger.info(f"Workspace initialized: {_workspace_root}")
    return _workspace_root


def root() -> Path:
    """Get the workspace root path."""
    if _workspace_root is None:
        # Fallback: use current directory (Docker or un-initialized)
        return Path.cwd()
    return _workspace_root


def path(*parts: str) -> Path:
    """Resolve a path relative to the workspace.

    Examples:
        workspace.path("knowledge")           → ~/jarvis-workspace/knowledge
        workspace.path("data", "memory.db")   → ~/jarvis-workspace/data/memory.db
        workspace.path("projects", "my-app")  → ~/jarvis-workspace/projects/my-app
    """
    return root() / Path(*parts)

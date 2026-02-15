"""Knowledge Manager — disk-based persistent knowledge system.

Implements the "discipline" approach to memory:
1. Read knowledge files before every response (recall)
2. Update knowledge files after every response (learn)

Knowledge lives on disk as markdown files:
  knowledge/
  ├── user-profile.md    — who the user is, preferences, communication style
  ├── learnings.md       — errors encountered, solutions found
  ├── decisions.md       — important decisions and their reasoning
  ├── context.md         — ongoing projects, topics, active tasks
  └── {custom}.md        — auto-created per domain/topic

This is inspired by Viktor's SKILL.md system — simple files that are
read before acting and updated after acting. The discipline is what
makes it work, not the database.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.knowledge")

# Default knowledge files with initial content
DEFAULT_FILES = {
    "user-profile.md": """# User Profile

## Preferences
- (none yet)

## Communication Style
- (not yet observed)

## Important Info
- (none yet)

---
*Auto-updated by Jarvis after conversations.*
""",
    "learnings.md": """# Learnings & Solutions

## Errors Encountered
(none yet)

## What Works Well
(none yet)

## What to Avoid
(none yet)

---
*Auto-updated by Jarvis when things go wrong or right.*
""",
    "decisions.md": """# Decisions Log

(no decisions logged yet)

---
*Auto-updated by Jarvis when important decisions are made.*
""",
    "context.md": """# Active Context

## Current Projects
(none yet)

## Recent Topics
(none yet)

## Pending Tasks
(none yet)

---
*Auto-updated by Jarvis to maintain continuity between conversations.*
""",
}


class KnowledgeManager:
    """Manages disk-based knowledge files for persistent agent memory."""

    def __init__(self, config: dict, knowledge_dir: str = None):
        self.config = config
        if knowledge_dir:
            self.knowledge_dir = Path(knowledge_dir)
        else:
            from jarvis import workspace
            self.knowledge_dir = workspace.path("knowledge")
        self._cache: dict[str, str] = {}  # filename -> content
        self._last_loaded: dict[str, datetime] = {}

    async def initialize(self):
        """Create knowledge directory and default files if missing."""
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        for filename, default_content in DEFAULT_FILES.items():
            filepath = self.knowledge_dir / filename
            if not filepath.exists():
                filepath.write_text(default_content, encoding="utf-8")
                logger.info(f"Created knowledge file: {filename}")

        # Load all into cache
        await self._load_all()
        logger.info(
            f"Knowledge loaded: {len(self._cache)} files, "
            f"{sum(len(v) for v in self._cache.values())} chars"
        )

    async def _load_all(self):
        """Load all knowledge files into cache."""
        self._cache.clear()
        for path in sorted(self.knowledge_dir.glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
                self._cache[path.name] = content
                self._last_loaded[path.name] = datetime.now()
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")

    # ── RECALL — Read Before Acting ──────────────────────────

    async def recall(self, message: str) -> dict[str, str]:
        """Gather relevant knowledge before responding.

        Returns a dict of filename -> content for files that are
        relevant to the current message.
        """
        # Always include user profile and active context
        relevant = {}

        # Core files — always loaded
        for core_file in ["user-profile.md", "context.md"]:
            if core_file in self._cache:
                relevant[core_file] = self._cache[core_file]

        # Keyword-based relevance for other files
        message_lower = message.lower()
        relevance_keywords = {
            "learnings.md": ["error", "bug", "fix", "problem", "issue", "broken",
                             "doesn't work", "failed", "crash", "wrong", "help",
                             "how to", "why", "eroare", "nu merge", "problemă"],
            "decisions.md": ["decide", "should", "choice", "option", "strategy",
                             "plan", "approach", "decizie", "alegere", "strategie"],
        }

        for filename, keywords in relevance_keywords.items():
            if filename in self._cache:
                if any(kw in message_lower for kw in keywords):
                    relevant[filename] = self._cache[filename]

        # Also include any custom knowledge files if they match topic words
        message_words = set(re.findall(r'\w+', message_lower))
        for filename, content in self._cache.items():
            if filename not in relevant and filename not in DEFAULT_FILES:
                # Custom file — check if topic matches
                file_topic = filename.replace(".md", "").replace("-", " ").lower()
                topic_words = set(file_topic.split())
                if topic_words & message_words:
                    relevant[filename] = content

        return relevant

    def get_all_knowledge(self) -> dict[str, str]:
        """Get all knowledge files (used at startup for system prompt)."""
        return dict(self._cache)

    def get_user_profile(self) -> str:
        """Get user profile content."""
        return self._cache.get("user-profile.md", "")

    def get_active_context(self) -> str:
        """Get active context content."""
        return self._cache.get("context.md", "")

    # ── LEARN — Write After Acting ───────────────────────────

    async def learn(self, llm, user_msg: str, assistant_msg: str, tools_used: list[str]):
        """Extract and persist knowledge from a conversation turn.

        This is the 'discipline' step — after every interaction, we:
        1. Extract structured knowledge (via LLM)
        2. Update the appropriate knowledge files on disk
        """
        try:
            extraction = await llm.chat(
                messages=[
                    {"role": "system", "content": self._learning_prompt()},
                    {"role": "user", "content": (
                        f"USER MESSAGE: {user_msg}\n\n"
                        f"ASSISTANT RESPONSE: {assistant_msg[:2000]}\n\n"
                        f"TOOLS USED: {', '.join(tools_used) if tools_used else 'none'}"
                    )},
                ],
                temperature=0.2,
                max_tokens=800,
            )

            text = extraction.get("text", "")
            updates = self._parse_learning_output(text)

            if not updates:
                return

            for filename, entries in updates.items():
                if entries:
                    await self._append_to_file(filename, entries)
                    logger.info(f"Knowledge updated: {filename} (+{len(entries)} entries)")

        except Exception as e:
            logger.debug(f"Learning step skipped: {e}")

    def _learning_prompt(self) -> str:
        """System prompt for knowledge extraction."""
        return """You analyze conversations and extract knowledge to remember.

Output a JSON object where keys are filenames and values are arrays of strings to append.
Only include files that need updating. Be selective — only genuinely important info.

Available files:
- "user-profile.md": User preferences, habits, info (e.g., "Prefers dark mode", "Uses VPS on Hetzner")
- "learnings.md": Errors/solutions (e.g., "ChromaDB fails on ARM — use SQLite FTS5 instead")
- "decisions.md": Important decisions (e.g., "2024-01-15: Chose SQLite over PostgreSQL for simplicity")
- "context.md": Active projects/topics (e.g., "Working on: Jarvis OS v1.0 launch")

Rules:
- Return {} (empty JSON) if nothing important to remember
- Each entry should be a complete, standalone sentence
- Prefix decisions with date
- Don't store trivial things (greetings, small talk)
- Don't duplicate info that's already likely stored
- Write entries in the same language the user speaks

Example output:
{"user-profile.md": ["Prefers Romanian language for communication"], "context.md": ["Working on: optimizing Jarvis memory system"]}"""

    def _parse_learning_output(self, text: str) -> dict[str, list[str]]:
        """Parse the LLM's learning extraction output."""
        try:
            # Try direct JSON parse
            data = json.loads(text)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(v, list)}
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    return {k: v for k, v in data.items() if isinstance(v, list)}
            except json.JSONDecodeError:
                pass

        # Try finding any JSON object in the text
        brace_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if brace_match:
            try:
                data = json.loads(brace_match.group(0))
                if isinstance(data, dict):
                    return {k: v for k, v in data.items() if isinstance(v, list)}
            except json.JSONDecodeError:
                pass

        return {}

    async def _append_to_file(self, filename: str, entries: list[str]):
        """Append new entries to a knowledge file."""
        filepath = self.knowledge_dir / filename

        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
        else:
            content = f"# {filename.replace('.md', '').replace('-', ' ').title()}\n\n"

        # Remove placeholder lines
        content = re.sub(r'\(none yet\)\n?', '', content)
        content = re.sub(r'\(no decisions logged yet\)\n?', '', content)
        content = re.sub(r'\(not yet observed\)\n?', '', content)

        # Find insertion point (before the --- footer)
        footer_match = re.search(r'\n---\n\*Auto-updated', content)
        if footer_match:
            insert_pos = footer_match.start()
            before = content[:insert_pos].rstrip()
            after = content[insert_pos:]
        else:
            before = content.rstrip()
            after = ""

        # Add new entries with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_lines = []
        for entry in entries:
            entry = entry.strip()
            if entry:
                new_lines.append(f"- [{timestamp}] {entry}")

        if new_lines:
            updated = before + "\n" + "\n".join(new_lines) + "\n" + after
            filepath.write_text(updated, encoding="utf-8")
            self._cache[filename] = updated

    # ── CONSOLIDATE — Periodic Cleanup ───────────────────────

    async def consolidate(self, llm):
        """Merge, deduplicate, and summarize knowledge files.

        Should be run periodically (e.g., daily via cron) to keep
        knowledge files clean and prevent unbounded growth.
        """
        for filename in list(self._cache.keys()):
            content = self._cache[filename]

            # Only consolidate files that are getting long
            if len(content) < 3000:
                continue

            try:
                result = await llm.chat(
                    messages=[
                        {"role": "system", "content": (
                            "You are a knowledge consolidation agent. "
                            "Given a knowledge file with potentially duplicate or verbose entries, "
                            "rewrite it to be concise and organized. "
                            "Remove duplicates, merge similar entries, keep the most recent/relevant info. "
                            "Maintain the markdown format with headers and bullet points. "
                            "Keep the footer line intact. "
                            "Preserve timestamps for the most recent version of each fact."
                        )},
                        {"role": "user", "content": f"Consolidate this file:\n\n{content}"},
                    ],
                    temperature=0.2,
                    max_tokens=2000,
                )

                consolidated = result.get("text", "")
                if consolidated and len(consolidated) > 100:
                    filepath = self.knowledge_dir / filename
                    filepath.write_text(consolidated, encoding="utf-8")
                    self._cache[filename] = consolidated
                    logger.info(
                        f"Consolidated {filename}: {len(content)} → {len(consolidated)} chars"
                    )

            except Exception as e:
                logger.warning(f"Consolidation failed for {filename}: {e}")

    # ── UTILITIES ────────────────────────────────────────────

    def format_for_prompt(self, knowledge: dict[str, str]) -> str:
        """Format knowledge dict into a string for the system prompt."""
        if not knowledge:
            return ""

        parts = ["## Your Knowledge (read from disk)\n"]
        for filename, content in knowledge.items():
            # Strip the auto-updated footer for cleaner prompt
            clean = re.sub(r'\n---\n\*Auto-updated.*$', '', content, flags=re.DOTALL)
            # Strip default empty content
            if "(none yet)" in clean and clean.count("(none yet)") > 2:
                continue  # Skip mostly-empty files
            parts.append(f"### {filename}\n{clean.strip()}\n")

        return "\n".join(parts)

    async def get_stats(self) -> dict:
        """Get knowledge system statistics."""
        total_entries = 0
        file_stats = {}
        for filename, content in self._cache.items():
            entries = content.count("\n- [")
            total_entries += entries
            file_stats[filename] = {
                "size_chars": len(content),
                "entries": entries,
            }

        return {
            "total_files": len(self._cache),
            "total_entries": total_entries,
            "total_chars": sum(len(v) for v in self._cache.values()),
            "files": file_stats,
        }

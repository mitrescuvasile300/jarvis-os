"""Jarvis Memory Store — 4-layer memory system.

Layers:
1. Short-term: Current conversation context (in-memory)
2. Working: Active task state (SQLite)
3. Long-term: Facts, decisions, preferences (SQLite)
4. Semantic: SQLite FTS5 full-text search (zero dependencies)

Optional: Install chromadb for vector-based semantic search.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.memory")


class MemoryStore:
    def __init__(self, config: dict):
        self.config = config
        self.backend = config.get("backend", "sqlite")
        self.retention_days = config.get("retention_days", 365)
        self.db_path = Path("data/memory.db")
        self.db: sqlite3.Connection | None = None
        self.chroma_client = None
        self.chroma_collection = None
        self._has_fts = False

        # Short-term memory (in-memory per conversation)
        self._conversations: dict[str, list[dict]] = {}

    async def initialize(self):
        """Set up database and search."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # SQLite for structured storage
        self.db = sqlite3.connect(str(self.db_path))
        self.db.row_factory = sqlite3.Row
        self._create_tables()

        # Try ChromaDB first (optional, for vector search)
        try:
            import chromadb
            import os
            chroma_host = os.environ.get("CHROMA_HOST") or self.config.get("chroma_host", "")
            chroma_port = int(os.environ.get("CHROMA_PORT", 0)) or self.config.get("chroma_port", 8000)

            if chroma_host:
                try:
                    self.chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
                    self.chroma_client.heartbeat()
                    logger.info(f"ChromaDB connected to {chroma_host}:{chroma_port}")
                except Exception:
                    persist_dir = str(Path("data/chroma"))
                    self.chroma_client = chromadb.PersistentClient(path=persist_dir)
            else:
                persist_dir = str(Path("data/chroma"))
                self.chroma_client = chromadb.PersistentClient(path=persist_dir)

            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"ChromaDB ready: {self.chroma_collection.count()} vectors")
        except ImportError:
            logger.info("ChromaDB not installed — using SQLite FTS5 for search (lightweight)")
        except Exception as e:
            logger.warning(f"ChromaDB failed: {e} — using SQLite FTS5 for search")

    def _create_tables(self):
        """Create SQLite tables."""
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                source TEXT DEFAULT '',
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS working_memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                task_id TEXT DEFAULT '',
                expires_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conv_id ON conversations(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_conv_ts ON conversations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_knowledge_cat ON knowledge(category);
        """)

        # FTS5 full-text search (built into SQLite, zero deps)
        try:
            self.db.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    content, type, source_id, timestamp
                );
            """)
            self._has_fts = True
        except Exception as e:
            logger.debug(f"FTS5 not available: {e}")
            self._has_fts = False

        self.db.commit()

    # ── Conversation Memory (Short-term) ──────────────────────

    async def store_message(self, conversation_id: str, role: str, content: str):
        """Store a conversation message."""
        msg_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        # SQLite
        self.db.execute(
            "INSERT INTO conversations (id, conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, timestamp),
        )
        self.db.commit()

        # In-memory cache
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        self._conversations[conversation_id].append({
            "role": role,
            "content": content,
            "timestamp": timestamp,
        })

        # Keep only last 50 messages in memory
        self._conversations[conversation_id] = self._conversations[conversation_id][-50:]

        # Index for search
        self._index_for_search(msg_id, content, "conversation", timestamp)

    async def get_conversation(self, conversation_id: str, limit: int = 20) -> list[dict]:
        """Get recent conversation messages."""
        # Try in-memory first
        if conversation_id in self._conversations:
            return self._conversations[conversation_id][-limit:]

        # Fall back to SQLite
        cursor = self.db.execute(
            "SELECT role, content, timestamp FROM conversations WHERE conversation_id = ? ORDER BY timestamp DESC LIMIT ?",
            (conversation_id, limit),
        )
        rows = cursor.fetchall()
        messages = [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]

        # Cache
        self._conversations[conversation_id] = messages
        return messages

    # ── Knowledge Memory (Long-term) ─────────────────────────

    async def store_knowledge(self, content: str, category: str = "general", source: str = ""):
        """Store a piece of knowledge."""
        knowledge_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        self.db.execute(
            "INSERT INTO knowledge (id, content, category, source, created_at, accessed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (knowledge_id, content, category, source, now, now),
        )
        self.db.commit()

        # Index for search
        self._index_for_search(knowledge_id, content, "knowledge", now)

        logger.debug(f"Knowledge stored: {content[:80]}...")

    # ── Working Memory (Task state) ──────────────────────────

    async def set_working(self, key: str, value: Any, task_id: str = "", ttl_minutes: int = 0):
        """Store a working memory entry (active task state)."""
        now = datetime.now()
        expires_at = (now + timedelta(minutes=ttl_minutes)).isoformat() if ttl_minutes else None

        self.db.execute(
            "INSERT OR REPLACE INTO working_memory (key, value, task_id, expires_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (key, json.dumps(value), task_id, expires_at, now.isoformat()),
        )
        self.db.commit()

    async def get_working(self, key: str) -> Any | None:
        """Retrieve a working memory entry."""
        cursor = self.db.execute("SELECT value, expires_at FROM working_memory WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            return None

        # Check expiry
        if row["expires_at"]:
            if datetime.fromisoformat(row["expires_at"]) < datetime.now():
                self.db.execute("DELETE FROM working_memory WHERE key = ?", (key,))
                self.db.commit()
                return None

        return json.loads(row["value"])

    # ── Search Indexing ─────────────────────────────────────

    def _index_for_search(self, source_id: str, content: str, doc_type: str, timestamp: str):
        """Index content for search (ChromaDB or FTS5)."""
        if self.chroma_collection:
            try:
                self.chroma_collection.add(
                    ids=[source_id],
                    documents=[content],
                    metadatas=[{"type": doc_type, "timestamp": timestamp}],
                )
            except Exception as e:
                logger.debug(f"ChromaDB index failed: {e}")

        if self._has_fts:
            try:
                self.db.execute(
                    "INSERT INTO memory_fts (content, type, source_id, timestamp) VALUES (?, ?, ?, ?)",
                    (content, doc_type, source_id, timestamp),
                )
                self.db.commit()
            except Exception as e:
                logger.debug(f"FTS index failed: {e}")

    # ── Semantic Search ──────────────────────────────────────

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search across all memory (vector or full-text)."""
        results = []

        # 1. ChromaDB vector search (if available)
        if self.chroma_collection:
            try:
                search_results = self.chroma_collection.query(
                    query_texts=[query],
                    n_results=min(limit, 20),
                )
                if search_results and search_results["documents"]:
                    for i, doc in enumerate(search_results["documents"][0]):
                        meta = search_results["metadatas"][0][i] if search_results["metadatas"] else {}
                        distance = search_results["distances"][0][i] if search_results.get("distances") else 0
                        results.append({
                            "content": doc,
                            "type": meta.get("type", "unknown"),
                            "relevance": round(1 - distance, 3),
                            "metadata": meta,
                        })
            except Exception as e:
                logger.debug(f"Vector search failed: {e}")

        # 2. SQLite FTS5 full-text search (fallback or supplement)
        if len(results) < limit and self._has_fts:
            remaining = limit - len(results)
            try:
                cursor = self.db.execute(
                    "SELECT content, type, source_id, rank FROM memory_fts WHERE memory_fts MATCH ? ORDER BY rank LIMIT ?",
                    (query, remaining),
                )
                for row in cursor.fetchall():
                    results.append({
                        "content": row["content"],
                        "type": row["type"],
                        "relevance": 0.7,
                        "metadata": {"source": "fts5"},
                    })
            except Exception:
                pass

        # 3. Simple LIKE fallback
        if len(results) < limit:
            remaining = limit - len(results)
            cursor = self.db.execute(
                "SELECT content, category, created_at FROM knowledge WHERE content LIKE ? ORDER BY accessed_at DESC LIMIT ?",
                (f"%{query}%", remaining),
            )
            for row in cursor.fetchall():
                results.append({
                    "content": row["content"],
                    "type": "knowledge",
                    "relevance": 0.5,
                    "metadata": {"category": row["category"]},
                })

        return results[:limit]

    # ── Utilities ────────────────────────────────────────────

    async def count(self) -> int:
        """Total memory entries."""
        cursor = self.db.execute("SELECT COUNT(*) as c FROM conversations")
        conversations = cursor.fetchone()["c"]
        cursor = self.db.execute("SELECT COUNT(*) as c FROM knowledge")
        knowledge = cursor.fetchone()["c"]
        return conversations + knowledge

    async def cleanup(self):
        """Remove expired entries."""
        if self.retention_days > 0:
            cutoff = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
            self.db.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff,))
            self.db.execute("DELETE FROM knowledge WHERE accessed_at < ?", (cutoff,))
            self.db.commit()
            logger.info(f"Cleaned up entries older than {self.retention_days} days")

        # Clean expired working memory
        now = datetime.now().isoformat()
        self.db.execute("DELETE FROM working_memory WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
        self.db.commit()

    async def close(self):
        """Close database connections."""
        if self.db:
            self.db.close()

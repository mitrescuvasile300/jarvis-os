"""Jarvis Memory Store — 4-layer memory system.

Layers:
1. Short-term: Current conversation context (in-memory)
2. Working: Active task state (SQLite)
3. Long-term: Facts, decisions, preferences (SQLite)
4. Semantic: Vector search over all knowledge (ChromaDB)
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

        # Short-term memory (in-memory per conversation)
        self._conversations: dict[str, list[dict]] = {}

    async def initialize(self):
        """Set up database and vector store."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # SQLite for structured storage
        self.db = sqlite3.connect(str(self.db_path))
        self.db.row_factory = sqlite3.Row
        self._create_tables()

        # ChromaDB for vector search
        vector_store = self.config.get("vector_store", "chromadb")
        if vector_store == "chromadb":
            try:
                import chromadb
                chroma_host = self.config.get("chroma_host", "chromadb")
                chroma_port = self.config.get("chroma_port", 8000)
                try:
                    self.chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
                except Exception:
                    # Fall back to persistent local
                    persist_dir = str(Path("data/chroma"))
                    self.chroma_client = chromadb.PersistentClient(path=persist_dir)

                self.chroma_collection = self.chroma_client.get_or_create_collection(
                    name="jarvis_memory",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"ChromaDB connected: {self.chroma_collection.count()} vectors")
            except ImportError:
                logger.warning("ChromaDB not installed — semantic search disabled")
            except Exception as e:
                logger.warning(f"ChromaDB connection failed: {e} — semantic search disabled")

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

        # Vector store
        if self.chroma_collection:
            try:
                self.chroma_collection.add(
                    ids=[msg_id],
                    documents=[content],
                    metadatas=[{
                        "type": "conversation",
                        "role": role,
                        "conversation_id": conversation_id,
                        "timestamp": timestamp,
                    }],
                )
            except Exception as e:
                logger.debug(f"Vector store failed: {e}")

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

        # Vector store for semantic search
        if self.chroma_collection:
            try:
                self.chroma_collection.add(
                    ids=[knowledge_id],
                    documents=[content],
                    metadatas=[{
                        "type": "knowledge",
                        "category": category,
                        "source": source,
                        "timestamp": now,
                    }],
                )
            except Exception as e:
                logger.debug(f"Vector store failed: {e}")

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

    # ── Semantic Search ──────────────────────────────────────

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Semantic search across all memory."""
        results = []

        # Vector search
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

        # Fall back / supplement with keyword search in SQLite
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

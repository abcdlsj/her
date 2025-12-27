"""Memory system for Her - stores conversations and explored information."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from her.sources.base import Item

DEFAULT_DB_PATH = Path.home() / ".her" / "memory.db"


@dataclass
class Message:
    """A conversation message."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime


class Memory:
    """Persistent memory storage using SQLite."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS explored_items (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT UNIQUE,
                source TEXT NOT NULL,
                summary TEXT,
                published_at TEXT,
                explored_at TEXT NOT NULL,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_digest (
                id INTEGER PRIMARY KEY,
                date TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_explored_items_date ON explored_items(explored_at);
        """)
        self.conn.commit()

    def add_message(self, role: Literal["user", "assistant"], content: str):
        """Add a conversation message."""
        self.conn.execute(
            "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
            (role, content, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_recent_messages(self, limit: int = 20) -> list[Message]:
        """Get recent conversation messages."""
        rows = self.conn.execute(
            "SELECT role, content, timestamp FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

        return [
            Message(role=r[0], content=r[1], timestamp=datetime.fromisoformat(r[2]))
            for r in reversed(rows)
        ]

    def save_explored_items(self, items: list[Item]):
        """Save explored items to memory."""
        now = datetime.now().isoformat()
        for item in items:
            try:
                self.conn.execute(
                    """INSERT OR IGNORE INTO explored_items
                       (title, url, source, summary, published_at, explored_at, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.title,
                        item.url,
                        item.source,
                        item.summary,
                        item.published_at.isoformat() if item.published_at else None,
                        now,
                        json.dumps(item.metadata),
                    ),
                )
            except sqlite3.IntegrityError:
                pass
        self.conn.commit()

    def get_today_items(self) -> list[Item]:
        """Get items explored today."""
        today = datetime.now().date().isoformat()
        rows = self.conn.execute(
            """SELECT title, url, source, summary, published_at, metadata
               FROM explored_items WHERE explored_at LIKE ?""",
            (f"{today}%",),
        ).fetchall()

        return [
            Item(
                title=r[0],
                url=r[1],
                source=r[2],
                summary=r[3],
                published_at=datetime.fromisoformat(r[4]) if r[4] else None,
                metadata=json.loads(r[5]) if r[5] else {},
            )
            for r in rows
        ]

    def save_daily_digest(self, content: str):
        """Save today's digest."""
        today = datetime.now().date().isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO daily_digest (date, content, created_at)
               VALUES (?, ?, ?)""",
            (today, content, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_daily_digest(self, date: str | None = None) -> str | None:
        """Get digest for a specific date."""
        if date is None:
            date = datetime.now().date().isoformat()
        row = self.conn.execute(
            "SELECT content FROM daily_digest WHERE date = ?", (date,)
        ).fetchone()
        return row[0] if row else None

    def close(self):
        """Close database connection."""
        self.conn.close()

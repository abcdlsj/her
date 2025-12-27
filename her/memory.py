"""Memory system for Her - stores conversations and explored information."""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from her.sources.base import Item

DEFAULT_DB_PATH = Path.home() / ".her" / "memory.db"

SESSION_TIMEOUT_HOURS = 4


@dataclass
class Message:
    """A conversation message."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    session_id: str | None = None


@dataclass
class Session:
    """A conversation session."""

    id: str
    started_at: datetime
    ended_at: datetime | None = None
    summary: str | None = None


class Memory:
    """Persistent memory storage using SQLite."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._migrate_schema()
        self._current_session_id: str | None = None

    def _init_schema(self):
        """Initialize database schema."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                summary TEXT
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
            CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
            CREATE INDEX IF NOT EXISTS idx_explored_items_date ON explored_items(explored_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
        """)
        self.conn.commit()

    def _migrate_schema(self):
        """Migrate existing data if needed."""
        cursor = self.conn.execute("PRAGMA table_info(conversations)")
        columns = [row[1] for row in cursor.fetchall()]
        if "session_id" not in columns:
            self.conn.execute("ALTER TABLE conversations ADD COLUMN session_id TEXT")
            self.conn.commit()

    def create_session(self) -> Session:
        """Create a new conversation session."""
        session = Session(
            id=str(uuid.uuid4())[:8],
            started_at=datetime.now(),
        )
        self.conn.execute(
            "INSERT INTO sessions (id, started_at) VALUES (?, ?)",
            (session.id, session.started_at.isoformat()),
        )
        self.conn.commit()
        self._current_session_id = session.id
        return session

    def end_session(self, summary: str | None = None) -> None:
        """End the current session."""
        if not self._current_session_id:
            return
        self.conn.execute(
            "UPDATE sessions SET ended_at = ?, summary = ? WHERE id = ?",
            (datetime.now().isoformat(), summary, self._current_session_id),
        )
        self.conn.commit()
        self._current_session_id = None

    def get_current_session(self) -> Session | None:
        """Get the current active session."""
        if not self._current_session_id:
            return None
        row = self.conn.execute(
            "SELECT id, started_at, ended_at, summary FROM sessions WHERE id = ?",
            (self._current_session_id,),
        ).fetchone()
        if row:
            return Session(
                id=row[0],
                started_at=datetime.fromisoformat(row[1]),
                ended_at=datetime.fromisoformat(row[2]) if row[2] else None,
                summary=row[3],
            )
        return None

    def get_last_session(self) -> Session | None:
        """Get the most recent completed session."""
        row = self.conn.execute(
            """SELECT id, started_at, ended_at, summary FROM sessions
               WHERE ended_at IS NOT NULL
               ORDER BY started_at DESC LIMIT 1"""
        ).fetchone()
        if row:
            return Session(
                id=row[0],
                started_at=datetime.fromisoformat(row[1]),
                ended_at=datetime.fromisoformat(row[2]) if row[2] else None,
                summary=row[3],
            )
        return None

    def get_session_messages(self, session_id: str) -> list[Message]:
        """Get messages from a specific session."""
        rows = self.conn.execute(
            """SELECT role, content, timestamp, session_id FROM conversations
               WHERE session_id = ? ORDER BY id ASC""",
            (session_id,),
        ).fetchall()
        return [
            Message(
                role=r[0],
                content=r[1],
                timestamp=datetime.fromisoformat(r[2]),
                session_id=r[3],
            )
            for r in rows
        ]

    def should_start_new_session(self) -> bool:
        """Check if we should start a new session based on timeout."""
        row = self.conn.execute(
            "SELECT timestamp FROM conversations ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return True
        last_time = datetime.fromisoformat(row[0])
        return datetime.now() - last_time > timedelta(hours=SESSION_TIMEOUT_HOURS)

    def add_message(self, role: Literal["user", "assistant"], content: str):
        """Add a conversation message."""
        self.conn.execute(
            "INSERT INTO conversations (role, content, timestamp, session_id) VALUES (?, ?, ?, ?)",
            (role, content, datetime.now().isoformat(), self._current_session_id),
        )
        self.conn.commit()

    def get_recent_messages(self, limit: int = 20) -> list[Message]:
        """Get recent conversation messages."""
        rows = self.conn.execute(
            "SELECT role, content, timestamp, session_id FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

        return [
            Message(
                role=r[0],
                content=r[1],
                timestamp=datetime.fromisoformat(r[2]),
                session_id=r[3],
            )
            for r in reversed(rows)
        ]

    def get_recent_sessions(self, limit: int = 5) -> list[Session]:
        """Get recent sessions with summaries."""
        rows = self.conn.execute(
            """SELECT id, started_at, ended_at, summary FROM sessions
               ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            Session(
                id=r[0],
                started_at=datetime.fromisoformat(r[1]),
                ended_at=datetime.fromisoformat(r[2]) if r[2] else None,
                summary=r[3],
            )
            for r in rows
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

    def get_cached_items(self, limit: int = 50) -> list[Item]:
        """Get recently cached items for quick greeting."""
        rows = self.conn.execute(
            """SELECT title, url, source, summary, published_at, metadata
               FROM explored_items ORDER BY explored_at DESC LIMIT ?""",
            (limit,),
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
        if self._current_session_id:
            self.end_session()
        self.conn.close()

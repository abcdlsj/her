"""Memory system for Her - stores conversations, explored items, and intents."""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from her.core.intent import Intent, IntentType

DEFAULT_DB_PATH = Path.home() / ".her" / "memory.db"
DEFAULT_HISTORY_DIR = Path.home() / ".her" / "history"
SESSIONS_FILE = DEFAULT_HISTORY_DIR / "sessions.json"
SESSION_TIMEOUT_HOURS = 4


@dataclass
class Item:
    """An explored item."""

    title: str
    url: str
    source: str
    summary: str | None = None
    published_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Message:
    """A conversation message."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime


@dataclass
class Session:
    """A conversation session."""

    id: str
    started_at: datetime
    ended_at: datetime | None = None
    summary: str | None = None
    messages: list[Message] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "summary": self.summary,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in self.messages
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            ended_at=datetime.fromisoformat(data["ended_at"])
            if data.get("ended_at")
            else None,
            summary=data.get("summary"),
            messages=[
                Message(
                    role=m["role"],
                    content=m["content"],
                    timestamp=datetime.fromisoformat(m["timestamp"]),
                )
                for m in data.get("messages", [])
            ],
        )


class Memory:
    """Persistent memory storage using SQLite for items and file system for history.

    Stores:
    - Conversations (messages) - file system (~/.her/history/)
    - Sessions (conversation groups) - file system (~/.her/history/sessions.json)
    - Explored items (from RSSHub) - SQLite
    - Daily digests - SQLite
    - Intent history (for display) - in-memory
    """

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        history_dir: Path = DEFAULT_HISTORY_DIR,
    ):
        self.db_path = db_path
        self.history_dir = history_dir

        history_dir.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

        self._current_session: Session | None = None
        self._intent_history: list[Intent] = []

    def _init_schema(self):
        """Initialize database schema for items and digests."""
        self.conn.executescript("""
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

            CREATE INDEX IF NOT EXISTS idx_explored_items_date ON explored_items(explored_at);
        """)
        self.conn.commit()

    # === Session Management (File System) ===

    def _load_sessions_index(self) -> list[dict]:
        """Load sessions index from file."""
        if not SESSIONS_FILE.exists():
            return []
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_sessions_index(self, sessions: list[dict]) -> None:
        """Save sessions index to file."""
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)

    def _load_session(self, session_id: str) -> Session | None:
        """Load a session from file."""
        session_file = self.history_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                return Session.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError):
            return None

    def _save_session(self, session: Session) -> None:
        """Save a session to file."""
        session_file = self.history_dir / f"{session.id}.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def create_session(self) -> Session:
        """Create a new conversation session."""
        session = Session(
            id=str(uuid.uuid4())[:8],
            started_at=datetime.now(),
        )
        self._current_session = session
        self._intent_history.clear()
        return session

    def end_session(self, summary: str | None = None) -> None:
        """End current session and save."""
        if not self._current_session:
            return

        session = self._current_session
        session.ended_at = datetime.now()
        session.summary = summary

        self._save_session(session)

        sessions = self._load_sessions_index()
        sessions.append(
            {
                "id": session.id,
                "started_at": session.started_at.isoformat(),
                "ended_at": session.ended_at.isoformat(),
                "summary": session.summary,
            }
        )
        sessions.sort(key=lambda x: x["started_at"], reverse=True)
        self._save_sessions_index(sessions)

        self._current_session = None

    def get_current_session(self) -> Session | None:
        """Get current active session."""
        return self._current_session

    def get_last_session(self) -> Session | None:
        """Get most recent completed session."""
        sessions = self._load_sessions_index()
        if not sessions:
            return None
        return self._load_session(sessions[0]["id"])

    def get_history_context(self, limit: int = 3) -> str:
        """Get context from recent sessions for LLM.

        Returns formatted context with session summaries.
        """
        sessions = self._load_sessions_index()[:limit]

        if not sessions:
            return "（这是第一次对话）"

        lines = ["最近几次对话:"]
        for i, s in enumerate(sessions, 1):
            summary = s.get("summary", "无记录")
            lines.append(f"{i}. {summary}")

        return "\n".join(lines)

    def should_start_new_session(self) -> bool:
        """Check if we should start a new session based on timeout."""
        if not self._current_session:
            return True

        elapsed = datetime.now() - self._current_session.started_at
        return elapsed > timedelta(hours=SESSION_TIMEOUT_HOURS)

    # === Message Management (File System) ===

    def add_message(self, role: Literal["user", "assistant"], content: str):
        """Add a conversation message to current session."""
        if not self._current_session:
            self.create_session()

        session = self._current_session
        if not session:
            return

        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now(),
        )
        session.messages.append(message)

        self._save_session(session)

    def get_recent_messages(self, limit: int = 20) -> list[Message]:
        """Get recent conversation messages from current and last sessions."""
        messages = []

        if self._current_session and self._current_session.messages:
            messages.extend(self._current_session.messages[-limit:])

        if len(messages) < limit:
            last_session = self.get_last_session()
            if last_session and last_session.messages:
                remaining = limit - len(messages)
                messages.extend(last_session.messages[-remaining:])

        return messages[-limit:]

    # === Item Management (SQLite) ===

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
        """Get recently cached items."""
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

    # === Digest Management (SQLite) ===

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

    # === Intent Management (In-memory) ===

    def add_intent(self, intent: Intent) -> None:
        """Add an intent to history (in-memory for current session)."""
        self._intent_history.append(intent)

    def get_recent_intents(self, limit: int = 20) -> list[Intent]:
        """Get recent intents for display."""
        return self._intent_history[-limit:]

    def get_intent_summary(self) -> str:
        """Get a text summary of recent intents."""
        if not self._intent_history:
            return "暂无意图记录"

        lines = []
        for intent in self._intent_history[-10:]:
            time_str = intent.timestamp.strftime("%H:%M")
            lines.append(f"[{time_str}] {intent.type.value}: {intent.reason[:30]}")
        return "\n".join(lines)

    # === Cleanup ===

    def close(self):
        """Close database connection and save current session."""
        if self._current_session:
            self.end_session()
        self.conn.close()

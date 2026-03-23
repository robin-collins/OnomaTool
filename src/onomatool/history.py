"""Rename history database for undo capability.

SQLite database at ~/.onoma_history.db tracks all rename operations
organized by session, enabling targeted undo.
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.expanduser("~/.onoma_history.db")
DEFAULT_RETENTION_DAYS = 90

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    working_dir TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS renames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    original_path TEXT NOT NULL,
    new_path TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""


class RenameHistory:
    """Manages the rename history SQLite database."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_CREATE_TABLES)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def create_session(self, working_dir: str) -> int:
        """Create a new rename session, returns session ID."""
        conn = self._connect()
        cursor = conn.execute(
            "INSERT INTO sessions (timestamp, working_dir, file_count) VALUES (?, ?, 0)",
            (datetime.now().isoformat(), working_dir),
        )
        conn.commit()
        return cursor.lastrowid

    def record_rename(
        self,
        session_id: int,
        original_path: str,
        new_path: str,
        status: str = "ok",
    ) -> None:
        """Record a rename operation in the history."""
        conn = self._connect()
        conn.execute(
            "INSERT INTO renames (session_id, original_path, new_path, timestamp, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, original_path, new_path, datetime.now().isoformat(), status),
        )
        conn.execute(
            "UPDATE sessions SET file_count = file_count + 1 WHERE id = ?",
            (session_id,),
        )
        conn.commit()

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List recent rename sessions."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, timestamp, working_dir, file_count FROM sessions "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_session_renames(self, session_id: int) -> list[dict]:
        """Get all renames for a session."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, original_path, new_path, timestamp, status FROM renames "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_session_id(self) -> int | None:
        """Get the most recent session ID."""
        conn = self._connect()
        row = conn.execute(
            "SELECT id FROM sessions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def undo_session(self, session_id: int | None = None) -> list[dict]:
        """Undo renames from a session. Returns list of results.

        Each result has keys: original_path, new_path, status, message.
        """
        if session_id is None:
            session_id = self.get_latest_session_id()
            if session_id is None:
                return [{"status": "error", "message": "No sessions found in history"}]

        renames = self.get_session_renames(session_id)
        if not renames:
            return [
                {
                    "status": "error",
                    "message": f"No renames found for session {session_id}",
                }
            ]

        results = []
        # Undo in reverse order, only for successful renames
        renames = [r for r in renames if r.get("status") == "ok"]
        if not renames:
            return [
                {
                    "status": "error",
                    "message": f"No successful renames found for session {session_id}",
                }
            ]
        for rename in reversed(renames):
            original = rename["original_path"]
            new = rename["new_path"]

            if not os.path.exists(new):
                results.append(
                    {
                        "original_path": original,
                        "new_path": new,
                        "status": "warning",
                        "message": f"File not found: {new} (may have been moved or deleted)",
                    }
                )
                continue

            if os.path.exists(original):
                results.append(
                    {
                        "original_path": original,
                        "new_path": new,
                        "status": "error",
                        "message": f"Cannot undo: {original} already exists",
                    }
                )
                continue

            try:
                os.rename(new, original)
                # Mark as undone in DB so future undo won't re-process
                self._mark_rename_undone(rename["id"])
                results.append(
                    {
                        "original_path": original,
                        "new_path": new,
                        "status": "ok",
                        "message": f"{os.path.basename(new)} --> {os.path.basename(original)}",
                    }
                )
            except OSError as e:
                results.append(
                    {
                        "original_path": original,
                        "new_path": new,
                        "status": "error",
                        "message": f"Failed to undo {new}: {e}",
                    }
                )

        return results

    def _mark_rename_undone(self, rename_id: int) -> None:
        """Mark a single rename record as undone so it won't be re-processed."""
        conn = self._connect()
        conn.execute(
            "UPDATE renames SET status = 'undone' WHERE id = ?", (rename_id,)
        )
        conn.commit()

    def prune(self, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
        """Remove sessions older than retention_days. Returns count of pruned sessions."""
        conn = self._connect()
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        cursor = conn.execute("SELECT id FROM sessions WHERE timestamp < ?", (cutoff,))
        old_ids = [row["id"] for row in cursor.fetchall()]
        if not old_ids:
            return 0

        placeholders = ",".join("?" * len(old_ids))
        conn.execute(
            f"DELETE FROM renames WHERE session_id IN ({placeholders})", old_ids
        )
        conn.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", old_ids)
        conn.commit()
        logger.info(
            "Pruned %d old sessions (older than %d days)", len(old_ids), retention_days
        )
        return len(old_ids)

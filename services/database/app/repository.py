from shared.config.settings import Settings
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path


DB_PATH = Settings.DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class DatabaseRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ssh_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    username TEXT,
                    message TEXT
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    banned_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                )
                """
            )

            conn.commit()

    def log_event(self, event):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ssh_events (
                    event_type,
                    timestamp,
                    ip,
                    username,
                    message
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_type,
                    event.timestamp.isoformat(),
                    event.ip,
                    event.username,
                    event.message,
                ),
            )

            conn.commit()

    def add_ban(
        self,
        ip: str,
        reason: str,
        duration_seconds: int,
    ):
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=duration_seconds)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bans (
                    ip,
                    reason,
                    banned_at,
                    expires_at,
                    active
                )
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    ip,
                    reason,
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )

            conn.commit()

    def get_active_bans(self):
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT ip, reason, banned_at, expires_at
                FROM bans
                WHERE active = 1
                ORDER BY banned_at DESC
                """
            ).fetchall()

    def get_expired_bans(self):
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            return conn.execute(
                """
                SELECT id, ip
                FROM bans
                WHERE active = 1
                AND expires_at <= ?
                """,
                (now,),
            ).fetchall()

    def mark_unbanned(self, ban_id: int):
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE bans
                SET active = 0
                WHERE id = ?
                """,
                (ban_id,),
            )

            conn.commit()

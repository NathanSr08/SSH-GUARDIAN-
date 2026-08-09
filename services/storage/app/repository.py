import json
import sqlite3

from shared.config.settings import Settings


class StorageRepository:
    def __init__(self, db_path=None):
        self.db_path = (
            db_path
            if db_path is not None
            else Settings.DB_PATH
        )

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._init_db()

    def connect(self):
        conn = sqlite3.connect(
            self.db_path
        )

        conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        return conn

    def _init_db(self):
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    redis_id TEXT UNIQUE,
                    stream TEXT NOT NULL,
                    event_type TEXT,
                    ip TEXT,
                    username TEXT,
                    timestamp TEXT,
                    payload TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enriched_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    redis_id TEXT UNIQUE,
                    event_type TEXT,
                    ip TEXT,
                    username TEXT,
                    country TEXT,
                    country_code TEXT,
                    city TEXT,
                    isp TEXT,
                    timestamp TEXT,
                    payload TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    redis_id TEXT UNIQUE,
                    action TEXT NOT NULL,
                    ip TEXT,
                    reason TEXT,
                    attempts INTEGER,
                    expires_at TEXT,
                    payload TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS firewall_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    redis_id TEXT UNIQUE,
                    event_type TEXT,
                    ip TEXT,
                    reason TEXT,
                    payload TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save_ssh_event(
        self,
        redis_id,
        payload,
    ):
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO events (
                    redis_id,
                    stream,
                    event_type,
                    ip,
                    username,
                    timestamp,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    redis_id,
                    Settings.SSH_EVENTS_STREAM,
                    payload.get("event_type"),
                    payload.get("ip"),
                    payload.get("username"),
                    payload.get("timestamp"),
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                    ),
                ),
            )

    def save_enriched_event(
        self,
        redis_id,
        payload,
    ):
        geo = payload.get("geo") or {}

        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO enriched_events (
                    redis_id,
                    event_type,
                    ip,
                    username,
                    country,
                    country_code,
                    city,
                    isp,
                    timestamp,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    redis_id,
                    payload.get("event_type"),
                    payload.get("ip"),
                    payload.get("username"),
                    geo.get("country"),
                    geo.get("country_code"),
                    geo.get("city"),
                    geo.get("isp"),
                    payload.get("timestamp"),
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                    ),
                ),
            )

    def save_security_action(
        self,
        redis_id,
        payload,
    ):
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO security_actions (
                    redis_id,
                    action,
                    ip,
                    reason,
                    attempts,
                    expires_at,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    redis_id,
                    payload.get("action"),
                    payload.get("ip"),
                    payload.get("reason"),
                    payload.get("attempts"),
                    payload.get("expires_at"),
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                    ),
                ),
            )

    def save_firewall_event(
        self,
        redis_id,
        payload,
    ):
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO firewall_events (
                    redis_id,
                    event_type,
                    ip,
                    reason,
                    payload
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    redis_id,
                    payload.get("event_type"),
                    payload.get("ip"),
                    payload.get("reason"),
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                    ),
                ),
            )

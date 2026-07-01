import sqlite3
import json
import secrets
from contextlib import closing
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet


class UserStorage:
    def __init__(self, database_path: str, encryption_key: str) -> None:
        self.database_path = database_path
        self.cipher = Fernet(encryption_key.encode())

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    api_key BLOB NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS moderation_drafts (
                    token TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    signature TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    telegram_id INTEGER PRIMARY KEY,
                    business_place_id INTEGER,
                    business_place_address TEXT
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(user_preferences)").fetchall()
            }
            if "business_place_address" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN business_place_address TEXT"
                )
            connection.commit()

    def save_api_key(self, telegram_id: int, api_key: str) -> None:
        encrypted_key = self.cipher.encrypt(api_key.encode())
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO users (telegram_id, api_key)
                VALUES (?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    api_key = excluded.api_key,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, encrypted_key),
            )
            connection.commit()

    def get_api_key(self, telegram_id: int) -> str | None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                "SELECT api_key FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
        return self.cipher.decrypt(row[0]).decode() if row else None

    def delete_api_key(self, telegram_id: int) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
            connection.commit()

    def save_business_place_id(self, telegram_id: int, business_place_id: int) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO user_preferences (telegram_id, business_place_id)
                VALUES (?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    business_place_id = excluded.business_place_id
                """,
                (telegram_id, business_place_id),
            )
            connection.commit()

    def get_business_place_id(self, telegram_id: int) -> int | None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                "SELECT business_place_id FROM user_preferences WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        return row[0] if row else None

    def clear_business_place_id(self, telegram_id: int) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "UPDATE user_preferences SET business_place_id = NULL WHERE telegram_id = ?",
                (telegram_id,),
            )
            connection.commit()

    def save_business_place_address(self, telegram_id: int, address: str) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO user_preferences (telegram_id, business_place_address)
                VALUES (?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    business_place_address = excluded.business_place_address
                """,
                (telegram_id, address),
            )
            connection.commit()

    def get_business_place_address(self, telegram_id: int) -> str | None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                "SELECT business_place_address FROM user_preferences WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        return row[0] if row else None

    def create_moderation_draft(self, telegram_id: int, payload: dict) -> str:
        token = secrets.token_urlsafe(24)
        expires_at = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO moderation_drafts (token, telegram_id, payload, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, telegram_id, json.dumps(payload, ensure_ascii=False), expires_at),
            )
            connection.commit()
        return token

    def get_moderation_draft(self, token: str) -> dict | None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                """
                SELECT telegram_id, payload, signature, status, expires_at
                FROM moderation_drafts WHERE token = ?
                """,
                (token,),
            ).fetchone()
        if not row or datetime.fromisoformat(row[4]) < datetime.now(UTC):
            return None
        return {
            "telegram_id": row[0],
            "payload": json.loads(row[1]),
            "signature": row[2],
            "status": row[3],
            "expires_at": row[4],
        }

    def sign_moderation_draft(self, token: str, signature: str) -> bool:
        with closing(sqlite3.connect(self.database_path)) as connection:
            cursor = connection.execute(
                """
                UPDATE moderation_drafts
                SET signature = ?, status = 'SIGNED', updated_at = CURRENT_TIMESTAMP
                WHERE token = ? AND status = 'PENDING'
                """,
                (signature, token),
            )
            connection.commit()
        return cursor.rowcount == 1

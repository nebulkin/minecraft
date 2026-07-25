import sqlite3
from contextlib import closing

DB_PATH = "applications.db"


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clan_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                name TEXT,
                tag TEXT,
                leader_nick TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS whitelist_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                nickname TEXT,
                age TEXT,
                about TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def add_clan_application(user_id: int, username: str, name: str, tag: str, leader_nick: str) -> int:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.execute(
            "INSERT INTO clan_applications (user_id, username, name, tag, leader_nick) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, name, tag, leader_nick),
        )
        conn.commit()
        return cur.lastrowid


def add_whitelist_application(user_id: int, username: str, nickname: str, age: str, about: str) -> int:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.execute(
            "INSERT INTO whitelist_applications (user_id, username, nickname, age, about) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, nickname, age, about),
        )
        conn.commit()
        return cur.lastrowid


def get_clan_application(app_id: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM clan_applications WHERE id = ?", (app_id,)
        ).fetchone()


def get_whitelist_application(app_id: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM whitelist_applications WHERE id = ?", (app_id,)
        ).fetchone()


def set_clan_status(app_id: int, status: str):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("UPDATE clan_applications SET status = ? WHERE id = ?", (status, app_id))
        conn.commit()


def set_whitelist_status(app_id: int, status: str):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("UPDATE whitelist_applications SET status = ? WHERE id = ?", (status, app_id))
        conn.commit()

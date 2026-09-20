"""
Database manager for AZ 8D Audio Bot.
"""

import sqlite3
import time
from typing import Optional, Dict, Any
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                last_song_name TEXT,
                raw_audio_path TEXT,
                processed_audio_path TEXT,
                cover_art_path TEXT,
                selected_style TEXT DEFAULT 'style1_smooth_wave',
                custom_photo_path TEXT,
                updated_at REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                effect TEXT,
                visualizer_style TEXT,
                timestamp REAL
            )
        """)
        conn.commit()

def register_user(user_id: int, username: Optional[str], first_name: Optional[str]):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username or "", first_name or "Friend"))
        conn.commit()

def save_session(user_id: int, **kwargs):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM user_sessions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        now = time.time()
        
        if row:
            updates = []
            values = []
            for k, v in kwargs.items():
                updates.append(f"{k} = ?")
                values.append(v)
            updates.append("updated_at = ?")
            values.append(now)
            values.append(user_id)
            query = f"UPDATE user_sessions SET {', '.join(updates)} WHERE user_id = ?"
            cursor.execute(query, values)
        else:
            fields = ["user_id", "updated_at"] + list(kwargs.keys())
            placeholders = ["?", "?"] + ["?" for _ in kwargs]
            values = [user_id, now] + list(kwargs.values())
            query = f"INSERT INTO user_sessions ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(query, values)
        conn.commit()

def get_session(user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_sessions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def log_conversion(user_id: int, conv_type: str, effect: str, visualizer_style: Optional[str] = None):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO conversions (user_id, type, effect, visualizer_style, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, conv_type, effect, visualizer_style, time.time()))
        conn.commit()

def get_stats():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM conversions WHERE type = 'audio'")
        total_audio = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM conversions WHERE type = 'video'")
        total_video = cursor.fetchone()[0]
        return {
            "total_users": total_users,
            "total_audio": total_audio,
            "total_video": total_video,
            "total_conversions": total_audio + total_video
        }

init_db()

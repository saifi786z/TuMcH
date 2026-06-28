"""Database Manager"""
import sqlite3
import json
from datetime import datetime, timedelta
from config import DB_PATH, DEFAULT_FREE_DM_LIMIT

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Use f-string for DEFAULT value since SQLite doesn't support ? in CREATE TABLE
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_date TEXT,
                dm_limit INTEGER DEFAULT {DEFAULT_FREE_DM_LIMIT},
                dm_used INTEGER DEFAULT 0,
                premium_until TEXT,
                referred_by INTEGER,
                refer_count INTEGER DEFAULT 0,
                message_text TEXT,
                message_media TEXT,
                phone_number TEXT,
                session_string TEXT,
                is_logged_in INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_days INTEGER,
                amount REAL,
                utr TEXT,
                screenshot_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                approved_by INTEGER,
                approved_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS redeem_codes (
                code TEXT PRIMARY KEY,
                days INTEGER,
                uses_remaining INTEGER,
                created_by INTEGER,
                created_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_type TEXT,
                target_id INTEGER,
                success INTEGER,
                error TEXT,
                sent_at TEXT
            )
        """)

        # Default admin settings
        defaults = [
            ("welcome_image", ""),
            ("dashboard_image", ""),
            ("payment_image", ""),
            ("force_join_channel", "@your_channel"),
            ("update_channel", "@your_channel"),
            ("how_to_use", "How to use text..."),
            ("payment_upi", "your-upi@bank"),
        ]
        for k, v in defaults:
            cursor.execute("INSERT OR IGNORE INTO admin_settings (key, value) VALUES (?, ?)", (k, v))

        self.conn.commit()

    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
        return None

    def add_user(self, user_id, username, first_name, referred_by=None):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date, referred_by)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, first_name, datetime.now().isoformat(), referred_by))
        self.conn.commit()

    def update_user(self, user_id, **kwargs):
        cursor = self.conn.cursor()
        for key, value in kwargs.items():
            cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
        self.conn.commit()

    def get_setting(self, key):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM admin_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def set_setting(self, key, value):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO admin_settings (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def add_payment(self, user_id, plan_days, amount, utr, screenshot_file_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO payments (user_id, plan_days, amount, utr, screenshot_file_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, plan_days, amount, utr, screenshot_file_id, datetime.now().isoformat()))
        self.conn.commit()
        return cursor.lastrowid

    def get_payment(self, payment_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        row = cursor.fetchone()
        if row:
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
        return None

    def update_payment(self, payment_id, **kwargs):
        cursor = self.conn.cursor()
        for key, value in kwargs.items():
            cursor.execute(f"UPDATE payments SET {key} = ? WHERE id = ?", (value, payment_id))
        self.conn.commit()

    def create_redeem_code(self, code, days, uses, created_by):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO redeem_codes (code, days, uses_remaining, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (code, days, uses, created_by, datetime.now().isoformat()))
        self.conn.commit()

    def get_redeem_code(self, code):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM redeem_codes WHERE code = ?", (code,))
        row = cursor.fetchone()
        if row:
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
        return None

    def use_redeem_code(self, code):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE redeem_codes SET uses_remaining = uses_remaining - 1 WHERE code = ?", (code,))
        self.conn.commit()

    def log_sent(self, user_id, target_type, target_id, success, error=None):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO sent_logs (user_id, target_type, target_id, success, error, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, target_type, target_id, 1 if success else 0, error, datetime.now().isoformat()))
        self.conn.commit()

    def get_premium_status(self, user_id):
        user = self.get_user(user_id)
        if not user or not user.get("premium_until"):
            return None
        until = datetime.fromisoformat(user["premium_until"])
        if until > datetime.now():
            remaining = until - datetime.now()
            return remaining.days + 1
        return None

    def add_premium(self, user_id, days):
        user = self.get_user(user_id)
        current = datetime.now()
        if user and user.get("premium_until"):
            current_premium = datetime.fromisoformat(user["premium_until"])
            if current_premium > current:
                current = current_premium
        new_premium = current + timedelta(days=days)
        self.update_user(user_id, premium_until=new_premium.isoformat())

    def get_dm_limit(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return DEFAULT_FREE_DM_LIMIT
        premium = self.get_premium_status(user_id)
        if premium is not None:
            return float('inf')
        return max(0, user["dm_limit"] - user.get("dm_used", 0))

    def use_dm(self, user_id, count=1):
        user = self.get_user(user_id)
        if user:
            self.update_user(user_id, dm_used=user.get("dm_used", 0) + count)

# Global instance
db = Database()

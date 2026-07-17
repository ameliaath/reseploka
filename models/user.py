"""
models/user.py
──────────────
Model User untuk Flask-Login.
Berisi class User dan fungsi query yang berhubungan dengan tabel users.
"""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from models.database import get_db
import psycopg2

class User(UserMixin):
    """Representasi user yang sedang login."""
    def __init__(self, id, username, is_admin=False):
        self.id       = id
        self.username = username
        self.is_admin = bool(is_admin)

    def __repr__(self):
        return f'<User {self.username}>'


# ── Query functions ───────────────────────────────────────────────────────────

def find_by_id(user_id):
    conn = get_db()
    row  = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return User(row['id'], row['username'], row['is_admin']) if row else None


def find_by_username(username):
    conn = get_db()
    row  = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return row


def create_user(username, password, is_admin=False):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
            (username, generate_password_hash(password), int(is_admin))
        )
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_password(row, password):
    return check_password_hash(row['password'], password)


# ── Admin CRUD ────────────────────────────────────────────────────────────────

def get_all_users():
    conn  = get_db()
    rows  = conn.execute(
        'SELECT id, username, is_admin, created_at FROM users ORDER BY id'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_password(user_id, new_password):
    conn = get_db()
    conn.execute(
        'UPDATE users SET password=? WHERE id=?',
        (generate_password_hash(new_password), user_id)
    )
    conn.commit()
    conn.close()


def delete_user(user_id):
    """Hapus user dan semua data terkait."""
    conn = get_db()
    for tbl in ('favorites', 'notes', 'checklists', 'ratings', 'history',
                'preferences', 'flavor_profile'):
        try:
            conn.execute(f'DELETE FROM {tbl} WHERE user_id=?', (user_id,))
        except Exception:
            pass
    conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.commit()
    conn.close()


def set_admin_status(user_id, is_admin: bool):
    conn = get_db()
    conn.execute('UPDATE users SET is_admin=? WHERE id=?', (int(is_admin), user_id))
    conn.commit()
    conn.close()

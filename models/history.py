"""
models/history.py
─────────────────
Semua query yang berhubungan dengan tabel history (riwayat kunjungan resep).
"""
from datetime import datetime
from models.database import get_db


def add_history(user_id, recipe_id, title, category):
    """
    Tambah atau perbarui entri riwayat.
    - Hapus entri lama resep yang sama agar tidak duplikat.
    - Batasi maksimal 50 entri per user (hapus yang paling lama).
    """
    now = datetime.now().strftime('%d %b %Y %H:%M')
    conn = get_db()
    # Hapus entri lama resep yang sama
    conn.execute(
        'DELETE FROM history WHERE user_id=%s AND recipe_id=%s',
        (user_id, recipe_id)
    )
    # Tambah entri baru (paling atas)
    conn.execute(
        'INSERT INTO history (user_id, recipe_id, title, category, visited_at) VALUES (%s,%s,%s,%s,%s)',
        (user_id, recipe_id, title, category, now)
    )
    # Hapus yang sudah melewati batas 50
    old = conn.execute(
        'SELECT id FROM history WHERE user_id=%s ORDER BY id DESC OFFSET 50',
        (user_id,)
    ).fetchall()
    for r in old:
        conn.execute('DELETE FROM history WHERE id=%s', (r['id'],))
    conn.commit()
    conn.close()


def get_history(user_id):
    """Ambil riwayat user, diurutkan dari yang paling baru."""
    conn = get_db()
    rows = conn.execute(
        'SELECT recipe_id, title, category, visited_at FROM history WHERE user_id=%s ORDER BY id DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    return [
        {
            'id': r['recipe_id'],
            'title': r['title'],
            'category': r['category'],
            'visited_at': r['visited_at'],
        }
        for r in rows
    ]

"""
models/favorite.py
──────────────────
Semua query yang berhubungan dengan tabel favorites.
"""
from models.database import get_db


def get_favorites(user_id):
    """Kembalikan list recipe_id yang difavoritkan user."""
    conn = get_db()
    rows = conn.execute(
        'SELECT recipe_id FROM favorites WHERE user_id = %s', (user_id,)
    ).fetchall()
    conn.close()
    return [r['recipe_id'] for r in rows]


def toggle_favorite(user_id, recipe_id):
    """
    Tambah ke favorit kalau belum ada, hapus kalau sudah ada.
    Return: (is_favorite: bool, total_count: int)
    """
    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM favorites WHERE user_id=%s AND recipe_id=%s',
        (user_id, recipe_id)
    ).fetchone()

    if existing:
        conn.execute(
            'DELETE FROM favorites WHERE user_id=%s AND recipe_id=%s',
            (user_id, recipe_id)
        )
        is_fav = False
    else:
        conn.execute(
            'INSERT INTO favorites (user_id, recipe_id) VALUES (%s, %s)',
            (user_id, recipe_id)
        )
        is_fav = True

    conn.commit()
    count = conn.execute(
        'SELECT COUNT(*) as c FROM favorites WHERE user_id=%s', (user_id,)
    ).fetchone()['c']
    conn.close()
    return is_fav, count

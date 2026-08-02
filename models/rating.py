"""
models/rating.py
────────────────
Semua query yang berhubungan dengan tabel ratings dan preferences.
"""
from models.database import get_db


# ── Ratings ───────────────────────────────────────────────────────────────────

def get_ratings(user_id):
    """Kembalikan dict {recipe_id_str: stars} milik user."""
    conn = get_db()
    rows = conn.execute(
        'SELECT recipe_id, stars FROM ratings WHERE user_id=%s', (user_id,)
    ).fetchall()
    conn.close()
    return {str(r['recipe_id']): r['stars'] for r in rows}


def set_rating(user_id, recipe_id, stars):
    """
    Simpan atau update rating. Hanya menerima 0-5.
    Return: (stars, total_rated, avg)
    """
    if not (0 <= stars <= 5):
        raise ValueError('Stars harus antara 0 dan 5')

    conn = get_db()
    conn.execute(
        '''INSERT INTO ratings (user_id, recipe_id, stars) VALUES (%s,%s,%s)
           ON CONFLICT(user_id, recipe_id) DO UPDATE SET stars=excluded.stars''',
        (user_id, recipe_id, stars)
    )
    conn.commit()
    all_stars = [
        r['stars'] for r in conn.execute(
            'SELECT stars FROM ratings WHERE user_id=%s', (user_id,)
        ).fetchall()
    ]
    conn.close()
    avg = round(sum(all_stars) / len(all_stars), 2) if all_stars else 0
    return stars, len(all_stars), avg


# ── Preferences ───────────────────────────────────────────────────────────────

PREF_KEYS = ['vegetarian', 'no_spicy', 'no_seafood', 'no_gluten', 'no_nuts']


def get_preferences(user_id):
    """Kembalikan dict preferensi diet user."""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM preferences WHERE user_id=%s', (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return {k: bool(row[k]) for k in PREF_KEYS}
    return {k: False for k in PREF_KEYS}


def save_preferences(user_id, prefs: dict):
    """Simpan atau update preferensi diet user."""
    conn = get_db()
    conn.execute(
        '''INSERT INTO preferences (user_id, vegetarian, no_spicy, no_seafood, no_gluten, no_nuts)
           VALUES (%s,%s,%s,%s,%s,%s)
           ON CONFLICT(user_id) DO UPDATE SET
               vegetarian=excluded.vegetarian,
               no_spicy=excluded.no_spicy,
               no_seafood=excluded.no_seafood,
               no_gluten=excluded.no_gluten,
               no_nuts=excluded.no_nuts''',
        (
            user_id,
            int(prefs.get('vegetarian', False)),
            int(prefs.get('no_spicy', False)),
            int(prefs.get('no_seafood', False)),
            int(prefs.get('no_gluten', False)),
            int(prefs.get('no_nuts', False)),
        )
    )
    conn.commit()
    conn.close()

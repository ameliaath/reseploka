"""
routes/main.py
──────────────
Blueprint untuk halaman utama: beranda, kategori, favorit, riwayat, preferensi.
"""
from flask import Blueprint, render_template, request, url_for
from flask_login import login_required, current_user

from ml_engine import df, CATEGORY_IMAGES, CATEGORY_LABELS
from models.favorite import get_favorites
from models.rating   import get_ratings, get_preferences
from models.history  import get_history
from models.flavor   import get_flavor_profile

main_bp = Blueprint('main', __name__)


# ── Beranda ───────────────────────────────────────────────────────────────────

@main_bp.route('/')
@login_required
def index():
    categories = []
    for cat, img in CATEGORY_IMAGES.items():
        sample = df[df['Category'] == cat].nlargest(1, 'Loves').iloc[0]
        categories.append({
            'name'        : cat,
            'label'       : CATEGORY_LABELS.get(cat, cat.title()),
            'image'       : img,
            'sample_title': sample['Title'],
            'sample_id'   : int(sample['id']),
        })

    uid   = current_user.id
    favs  = get_favorites(uid)
    prefs = get_preferences(uid)
    return render_template('index.html',
        categories=categories,
        favorites_count=len(favs),
        prefs=prefs,
        total_recipes=len(df),
    )


# ── Kategori ──────────────────────────────────────────────────────────────────

@main_bp.route('/category/<cat_name>')
@login_required
def category(cat_name):
    sort_by = request.args.get('sort', '')
    cat_df  = df[df['Category'] == cat_name]

    if sort_by == 'loves_desc':   cat_df = cat_df.sort_values('Loves', ascending=False)
    elif sort_by == 'loves_asc':  cat_df = cat_df.sort_values('Loves', ascending=True)
    else:                         cat_df = cat_df.sort_values('Loves', ascending=False)

    recipes = [
        {
            'id'   : int(r['id']),
            'title': r['Title'],
            'loves': int(r['Loves']),
            'photo': r.get('Photo', '') or '',
        }
        for _, r in cat_df.head(50).iterrows()
    ]
    favs = get_favorites(current_user.id)
    return render_template('category.html',
        category_name =cat_name,
        category_label=CATEGORY_LABELS.get(cat_name, cat_name.title()),
        category_image=CATEGORY_IMAGES.get(cat_name, ''),
        recipes       =recipes,
        sort_by       =sort_by,
        favorites_count=len(favs),
    )


# ── Favorit ───────────────────────────────────────────────────────────────────

@main_bp.route('/favorites')
@login_required
def favorites():
    sort_by = request.args.get('sort', '')
    uid     = current_user.id
    fav_ids = get_favorites(uid)
    ratings = get_ratings(uid)

    fav = [
        {
            'id'      : int(df.iloc[fid]['id']),
            'title'   : df.iloc[fid]['Title'],
            'category': df.iloc[fid]['Category'],
            'loves'   : int(df.iloc[fid]['Loves']),
            'rating'  : ratings.get(str(fid), 0),
            'photo'   : df.iloc[fid].get('Photo', '') or '',
        }
        for fid in fav_ids if 0 <= fid < len(df)
    ]

    if sort_by == 'loves_desc':  fav.sort(key=lambda x: x['loves'], reverse=True)
    elif sort_by == 'loves_asc': fav.sort(key=lambda x: x['loves'])

    return render_template('favorites.html',
        recipes=fav,
        sort_by=sort_by,
        favorites_count=len(fav),
    )


# ── Riwayat ───────────────────────────────────────────────────────────────────

@main_bp.route('/riwayat')
@login_required
def riwayat():
    uid     = current_user.id
    history = get_history(uid)
    ratings = get_ratings(uid)

    for item in history:
        item['rating'] = ratings.get(str(item['id']), 0)
        rid = item['id']
        if 0 <= rid < len(df):
            item['photo'] = df.iloc[rid].get('Photo', '') or ''
        else:
            item['photo'] = ''

    return render_template('riwayat.html',
        history=history,
        favorites_count=len(get_favorites(uid)),
    )


# ── Preferensi (diet filter) ──────────────────────────────────────────────────

@main_bp.route('/preferensi')
@login_required
def preferensi():
    uid    = current_user.id
    prefs  = get_preferences(uid)
    flavor = get_flavor_profile(uid)
    return render_template('preferensi.html',
        prefs          =prefs,
        flavor         =flavor,
        favorites_count=len(get_favorites(uid)),
    )


# ── Preferensi Rasa — halaman standalone (tidak terikat resep tertentu) ───────

@main_bp.route('/rasa')
@login_required
def rasa_setting():
    """Setting preferensi rasa dari menu navbar / halaman preferensi."""
    uid    = current_user.id
    flavor = get_flavor_profile(uid)
    return render_template('rasa.html',
        flavor      =flavor,
        back_url    =url_for('main.preferensi'),
        from_recipe =False,
        favorites_count=len(get_favorites(uid)),
    )


# ── Preferensi Rasa — dibuka dari halaman resep tertentu ─────────────────────

@main_bp.route('/rasa/<int:recipe_id>')
@login_required
def rasa_from_recipe(recipe_id):
    """Setting preferensi rasa yang dibuka dari tombol di halaman resep."""
    if recipe_id < 0 or recipe_id >= len(df):
        return 'Resep tidak ditemukan', 404
    uid    = current_user.id
    flavor = get_flavor_profile(uid)
    return render_template('rasa.html',
        flavor      =flavor,
        back_url    =url_for('recipe.recipe', recipe_id=recipe_id),
        from_recipe =True,
        favorites_count=len(get_favorites(uid)),
    )

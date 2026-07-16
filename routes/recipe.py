"""
routes/recipe.py
────────────────
Blueprint untuk halaman resep dan pencarian.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from ml_engine      import df, search_recipes, get_recommendations, get_top_features
from models.favorite import get_favorites
from models.rating   import get_ratings, get_preferences
from models.note     import get_notes, get_checklist
from models.history  import add_history
from models.flavor   import get_flavor_profile, DEFAULT_SERVINGS

recipe_bp = Blueprint('recipe', __name__)


# ── Pencarian ─────────────────────────────────────────────────────────────────

@recipe_bp.route('/search')
@login_required
def search():
    query    = request.args.get('q', '').strip()
    sort_by  = request.args.get('sort', '')
    page     = int(request.args.get('page', 1))
    per_page = 20

    if not query:
        return jsonify({'results': [], 'total': 0, 'query': ''})

    uid   = current_user.id
    prefs = get_preferences(uid)

    results, total = search_recipes(query, sort_by, page, per_page, prefs)

    # Tambahkan data rating per user ke hasil
    ratings = get_ratings(uid)
    for r in results:
        r['rating'] = ratings.get(str(r['id']), 0)

    return jsonify({
        'results' : results,
        'total'   : total,
        'query'   : query,
        'page'    : page,
        'per_page': per_page,
    })


# ── Detail Resep ──────────────────────────────────────────────────────────────

@recipe_bp.route('/recipe/<int:recipe_id>')
@login_required
def recipe(recipe_id):
    if recipe_id < 0 or recipe_id >= len(df):
        return 'Resep tidak ditemukan', 404

    row = df.iloc[recipe_id]
    uid = current_user.id

    # Simpan ke riwayat
    add_history(uid, recipe_id, row['Title'], row['Category'])

    ingredients     = [i.strip() for i in str(row['Ingredients']).split('--') if i.strip()]
    steps           = [s.strip() for s in str(row['Steps']).split('--')       if s.strip()]
    recommendations = get_recommendations(recipe_id)
    top_features    = get_top_features(recipe_id)
    ratings         = get_ratings(uid)
    favs            = get_favorites(uid)
    flavor_profile  = get_flavor_profile(uid)
    # Porsi BUKAN preferensi global — tiap resep punya basis porsi sendiri
    # (bahan-bahan di dataset selalu ditulis untuk DEFAULT_SERVINGS). Kalau
    # dibiarkan pakai flavor_profile['servings'] apa adanya, porsi yang barusan
    # di-adjust di resep lain akan "kebawa" ke resep ini. Jadi override di sini,
    # supaya tiap resep selalu mulai dari basisnya sendiri.
    flavor_profile  = {**flavor_profile, 'servings': DEFAULT_SERVINGS}

    # Konteks asal navigasi: kalau dibuka dari hasil pencarian, breadcrumb
    # harus balik ke pencarian itu, bukan ke halaman kategori generik.
    from_search  = request.args.get('from') == 'search'
    search_query = request.args.get('q', '')

    return render_template('recipe.html',
        recipe={
            'id'      : recipe_id,
            'title'   : row['Title'],
            'category': row['Category'],
            'loves'   : int(row['Loves']),
            'url'     : row.get('URL', ''),
            'keywords': row.get('Keywords', ''),
            'photo'   : row.get('Photo', '') or '',
        },
        ingredients    =ingredients,
        steps          =steps,
        recommendations=recommendations,
        is_favorite    =(recipe_id in favs),
        notes          =get_notes(uid, recipe_id),
        checklists     =get_checklist(uid, recipe_id),
        user_rating    =ratings.get(str(recipe_id), 0),
        top_features   =top_features,
        flavor_profile =flavor_profile,
        from_search    =from_search,
        search_query   =search_query,
    )

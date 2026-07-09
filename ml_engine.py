"""
ml_engine.py
────────────
Dataset dan model TF-IDF dimuat SEKALI saat app start.
Semua route yang butuh data ML import dari sini — tidak ada duplikasi.

Kenapa dipisah?
- Dataset besar (ratusan ribu baris) = loading mahal, tidak boleh diulang.
- Blueprint tidak bisa load dataset sendiri-sendiri atau memori akan meledak.
- Satu sumber kebenaran untuk df, tfidf, tfidf_matrix, feature_names.
"""
import os
import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── Konstanta keyword ─────────────────────────────────────────────────────────
SPICY_KW   = ['cabai', 'cabe', 'rawit', 'sambal', 'pedas', 'lada merah']
SEAFOOD_KW = ['udang', 'cumi', 'kepiting', 'kerang', 'lobster', 'ikan', 'salmon', 'tongkol']
MEAT_KW    = ['ayam', 'sapi', 'kambing', 'babi', 'daging', 'bebek']
GLUTEN_KW  = ['tepung terigu', 'kecap', 'mie', 'makaroni']
NUT_KW     = ['kacang', 'almond', 'kenari', 'kemiri', 'mete']

CATEGORY_IMAGES = {
    'ayam'  : 'https://www.unileverfoodsolutions.co.id/dam/global-ufs/mcos/SEA/calcmenu/recipes/ID-recipes/chicken-&-other-poultry-dishes/fillet-ayam-goreng-renyah-dengan-mayones-kopi/main-header.jpg',
    'ikan'  : 'https://www.dapurkobe.co.id/wp-content/uploads/tenggiri-kuah-pedas.jpg',
    'kambing': 'https://www.dapurkobe.co.id/wp-content/uploads/sate-kambing-bumbu-kecap.jpg',
    'sapi'  : 'https://www.astronauts.id/blog/wp-content/uploads/2023/11/Resep-Sop-Iga-Sapi-Khas-Betawi-untuk-Makan-Siang-Keluarga-1.jpg',
    'tahu'  : 'https://img-global.cpcdn.com/recipes/489c4bd9cefaff4e/1200x630cq80/photo.jpg',
    'telur' : 'https://asset.kompas.com/crops/UCNW5kaOhr7MSTY8TNphg8L7CjM=/26x15:994x660/1200x800/data/photo/2022/04/02/624838fa00a5c.jpg',
    'tempe' : 'https://www.dapurkobe.co.id/wp-content/uploads/tempe-orek-pedas-step4.jpg',
    'udang' : 'https://www.dapurkobe.co.id/wp-content/uploads/udang-bakar-bumbu-rujak.jpg',
}

CATEGORY_LABELS = {
    'ayam'  : 'Ayam 🍗',
    'ikan'  : 'Ikan 🐟',
    'kambing': 'Kambing 🥩',
    'sapi'  : 'Sapi 🥩',
    'tahu'  : 'Tahu 🟨',
    'telur' : 'Telur 🍳',
    'tempe' : 'Tempe 🫘',
    'udang' : 'Udang 🦐',
}

# ── Helper preprocessing ──────────────────────────────────────────────────────

def _clean_ingredients(text):
    if pd.isna(text):
        return ''
    cleaned = []
    for item in str(text).split('--'):
        item = re.sub(
            r'\d+[\d/\s]*(gram|gr|kg|ml|liter|sdm|sdt|butir|lembar|buah|siung|'
            r'ruas|batang|ikat|ekor|helai|bungkus|sachet|ons|cc|L|g|mg|cm)?',
            '', item, flags=re.IGNORECASE
        )
        item = re.sub(r'\(.*?\)', '', item)
        item = re.sub(r'[^a-zA-Z\s]', '', item).strip().lower()
        if len(item) > 2:
            cleaned.append(item)
    return ' '.join(cleaned)


def _tag_recipe(ing_text):
    t = ing_text.lower()
    tags = set()
    if any(k in t for k in SPICY_KW):                          tags.add('spicy')
    if any(k in t for k in SEAFOOD_KW):                        tags.add('seafood')
    if not any(k in t for k in MEAT_KW + SEAFOOD_KW):          tags.add('vegetarian')
    if any(k in t for k in GLUTEN_KW):                         tags.add('gluten')
    if any(k in t for k in NUT_KW):                            tags.add('nuts')
    return tags


# ── Load dataset & fit model ──────────────────────────────────────────────────
_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'dataset-gabungan-clean.csv')

df = pd.read_csv(_DATA_PATH)
df = df.dropna(subset=['Title', 'Ingredients', 'Steps']).reset_index(drop=True)
df['Loves'] = pd.to_numeric(df['Loves'], errors='coerce').fillna(0).astype(int)
df['id']    = df.index
df['ingredients_clean'] = df['Ingredients'].apply(_clean_ingredients)
df['tags']              = df['Ingredients'].apply(lambda x: _tag_recipe(str(x)))
if 'Photo' not in df.columns:
    df['Photo'] = ''
df['Photo'] = df['Photo'].fillna('')

tfidf        = TfidfVectorizer(max_features=3000, ngram_range=(1, 2), min_df=2)
tfidf_matrix = tfidf.fit_transform(df['ingredients_clean'])
feature_names = np.array(tfidf.get_feature_names_out())


# ── Utility yang dipakai route ────────────────────────────────────────────────

def apply_preferences(results_df, prefs: dict):
    """Filter DataFrame resep berdasarkan preferensi diet user."""
    mask = []
    for _, row in results_df.iterrows():
        tags = row.get('tags', set())
        ok = True
        if prefs.get('vegetarian')  and 'vegetarian' not in tags: ok = False
        if prefs.get('no_spicy')    and 'spicy'      in tags:     ok = False
        if prefs.get('no_seafood')  and 'seafood'    in tags:     ok = False
        if prefs.get('no_gluten')   and 'gluten'     in tags:     ok = False
        if prefs.get('no_nuts')     and 'nuts'       in tags:     ok = False
        mask.append(ok)
    return results_df[mask]


def search_recipes(query: str, sort_by: str, page: int, per_page: int, prefs: dict):
    """
    Cari resep berdasarkan query bahan menggunakan cosine similarity TF-IDF.
    Return: (list[dict], total: int)
    """
    query_vec = tfidf.transform([query.lower()])
    scores    = cosine_similarity(query_vec, tfidf_matrix).flatten()
    top_idx   = np.where(scores > 0.01)[0]

    if len(top_idx) == 0:
        return [], 0

    rdf = df.iloc[top_idx].copy()
    rdf['similarity'] = scores[top_idx]
    rdf = apply_preferences(rdf, prefs)

    if sort_by == 'loves_desc':   rdf = rdf.sort_values('Loves', ascending=False)
    elif sort_by == 'loves_asc':  rdf = rdf.sort_values('Loves', ascending=True)
    else:                         rdf = rdf.sort_values('similarity', ascending=False)

    total = len(rdf)
    paged = rdf.iloc[(page - 1) * per_page: page * per_page]

    results = [
        {
            'id'        : int(r['id']),
            'title'     : r['Title'],
            'category'  : r['Category'],
            'loves'     : int(r['Loves']),
            'similarity': round(float(r['similarity']) * 100, 1),
            'photo'     : r.get('Photo', '') or CATEGORY_IMAGES.get(r['Category'], ''),
        }
        for _, r in paged.iterrows()
    ]
    return results, total


def get_recommendations(recipe_id: int, top_n: int = 6):
    """Hitung rekomendasi resep serupa berdasarkan cosine similarity."""
    scores = cosine_similarity(tfidf_matrix[recipe_id], tfidf_matrix).flatten()
    scores[recipe_id] = 0
    top = np.argsort(scores)[::-1][:top_n]
    return [
        {
            'id'        : int(df.iloc[i]['id']),
            'title'     : df.iloc[i]['Title'],
            'category'  : df.iloc[i]['Category'],
            'loves'     : int(df.iloc[i]['Loves']),
            'similarity': round(float(scores[i]) * 100, 1),
        }
        for i in top
    ]


def get_top_features(recipe_id: int, top_n: int = 8):
    """Ambil fitur TF-IDF tertinggi untuk satu resep (untuk tampilan kata kunci)."""
    vec = tfidf_matrix[recipe_id].toarray().flatten()
    idx = np.argsort(vec)[::-1][:top_n]
    return [
        {'term': feature_names[i], 'score': round(float(vec[i]) * 100, 1)}
        for i in idx if vec[i] > 0
    ]

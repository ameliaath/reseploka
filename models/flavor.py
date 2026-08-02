"""
models/flavor.py
────────────────
Profil rasa user (pedas, manis, gurih, asam) dan logika penyesuaian
takaran bahan berdasarkan preferensi rasa + jumlah porsi.

STRATEGI MATCHING (diperbaiki berdasarkan analisis dataset nyata):
- Matching dilakukan dengan regex word-boundary agar tidak false positive
- Setiap rasa punya dua level keyword:
    PRIMARY   → bahan utama pembawa rasa (bobot penuh)
    SECONDARY → bahan pelengkap rasa (bobot setengah)
- Kecap ASIN tidak dihitung sebagai MANIS
- "asam" standalone dikecualikan kalau diikuti kata netral (lemak, amino, urat)
"""
import re
from models.database import get_db

# ── Konstanta ──────────────────────────────────────────────────────────────────
DEFAULT_SERVINGS = 2

# Satuan baku dataset Indonesia
UNIT_PATTERN = re.compile(
    r'(\d+(?:[,/.]\d+)?)\s*'
    r'(sendok\s+makan|sendok\s+teh|sdm|sdt|gram|gr|kg|ml|liter|'
    r'ons|cc|g\b|mg|cm|butir|lembar|buah|siung|ruas|batang|ikat|'
    r'ekor|helai|bungkus|sachet|potong|iris|genggam|lbr|btr|bh\b|'
    r'sdt\b|sdm\b|l\b)?',
    re.IGNORECASE
)

# ── Keyword bank (dibangun dari analisis 207.969 entri bahan dataset nyata) ────
#
# Format tiap entry:
#   (regex_pattern, bobot)
#   bobot 1.0 = primary carrier (langsung mempengaruhi rasa)
#   bobot 0.5 = secondary / modifier (sedikit mempengaruhi)
#
# CATATAN PENTING:
#   - Pattern menggunakan re.search, BUKAN re.fullmatch
#   - Urutan list tidak berpengaruh; semua dievaluasi
#   - Satu bahan bisa match LEBIH DARI SATU flavor (misal sambal = pedas)

FLAVOR_KEYWORDS = {

    # ══════════════════════════════════════════════════════════════════════════
    # PEDAS  →  naikkan takaran bahan pembawa rasa pedas
    # ══════════════════════════════════════════════════════════════════════════
    'spicy': [
        # Cabe/Cabai – semua ejaan dan modifier (10.812 + 3.018 entri)
        (r'\bcab[ae]i?\b',           1.0),   # cabe, cabai, caba, cabei
        (r'\brawit\b',               1.0),   # cabe rawit (standalone juga ada)
        (r'\blombok\b',              1.0),   # lombok (197x)
        (r'\bcengek\b',              1.0),   # cengek (35x)
        # Lada & Merica (3.936 + 3.650 entri)
        (r'\bmerica\b',              1.0),
        (r'\blada\b',                1.0),   # lada hitam, lada putih, lada bubuk
        (r'\bsahang\b',              1.0),   # nama lain lada di Kalimantan (5x)
        (r'\bpepper\b',              0.8),   # pepper (35x)
        # Sambal & turunannya (1.012 entri)
        (r'\bsambal[a-z]*\b',        0.8),   # sambal, sambalado, sambalin
        # Saus pedas (29x + 39x + 49x)
        (r'\bsaus\s+pedas\b',        0.8),
        (r'\bsaos\s+pedas\b',        0.8),
        (r'\bsaus\s+cab[ae]i?\b',    0.8),
        (r'\bsaus\s+cabe\b',         0.8),
        (r'\bsaus\s+sambal\b',       0.7),   # saus sambal (190x)
        # Internasional / import (34x + 11x)
        (r'\bchil[il]i\b',           0.8),
        (r'\bjalapeno\b',            0.8),
        (r'\bhabanero\b',            0.8),
        (r'\bpaprika\b',             0.5),   # paprika mild, kadang tidak pedas
        # Cabe bubuk / kering (50x + 38x)
        (r'\bcabe?\s+bubuk\b',       0.9),
        (r'\bcabai?\s+bubuk\b',      0.9),
        (r'\bcabe?\s+kering\b',      0.7),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # MANIS  →  naikkan takaran bahan pembawa rasa manis
    # ══════════════════════════════════════════════════════════════════════════
    'sweet': [
        # Kecap manis (3.186x) — PERHATIAN: kecap asin & ikan TIDAK termasuk
        (r'\bkecap\s+manis\b',       1.0),
        (r'\bkecap\s+bango\b',       1.0),   # merek kecap manis (99x)
        (r'\bkecap\s+bangau\b',      1.0),   # (18x)
        (r'\bkecap\s+abc\b',         0.9),   # bisa manis/asin, anggap manis
        (r'\bkecap\b(?!\s+(asin|ikan|inggris|hitam|teriyaki|jamur|saori))',
                                     0.7),   # kecap polos tanpa modifier (1.143x)
        # Gula semua jenis (4.892 total entri)
        (r'\bgula\s+pasir\b',        1.0),   # gula pasir (paling umum)
        (r'\bgula\s+merah\b',        1.0),   # gula merah
        (r'\bgula\s+jawa\b',         1.0),   # gula jawa
        (r'\bgula\s+aren\b',         1.0),   # gula aren (42x)
        (r'\bgula\s+palem\b',        1.0),   # gula palem (16x)
        (r'\bgula\s+kelapa\b',       1.0),
        (r'\bgula\s+putih\b',        1.0),
        (r'\bgula\b',                0.9),   # gula standalone (775x)
        # Madu & sirup (151x + 5x)
        (r'\bmadu\b',                1.0),
        (r'\bsirup\b',               0.9),
        (r'\bsyrup\b',               0.9),
        # Saus manis
        (r'\bsaus\s+asam\s+manis\b', 0.7),  # saus asam manis (20x)
        (r'\bsaus\s+teriyaki\b',     0.7),  # (150x) – manis
        (r'\bsaus\s+barbeque\b',     0.6),
        (r'\bsaus\s+bbq\b',          0.6),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # GURIH  →  naikkan takaran bahan pembawa rasa umami/gurih
    # ══════════════════════════════════════════════════════════════════════════
    'savory': [
        # Garam (sangat umum, hampir di semua resep)
        (r'\bgaram\b',               1.0),
        # Penyedap – merek & generik (3.347 + 1.047 + 608 + 171 + 105 ... entri)
        (r'\bpenyedap\b',            1.0),
        (r'\broyco\b',               1.0),
        (r'\bmasako\b',              1.0),
        (r'\bsasa\b',                1.0),
        (r'\bmicin\b',               1.0),
        (r'\bmsg\b',                 1.0),
        (r'\bvetsin\b',              1.0),
        (r'\bajinomoto\b',           1.0),
        (r'\bmaggi\b',               0.9),
        (r'\bknorr\b',               0.9),
        # Kaldu (2.468 entri)
        (r'\bkaldu\b',               1.0),   # kaldu ayam, sapi, jamur
        # Terasi / belacan (611 + 41 + 2 entri)
        (r'\bterasi\b',              1.0),
        (r'\btrasi\b',               1.0),
        (r'\bbelacan\b',             1.0),
        # Kecap asin (661x) & kecap ikan (154x) → gurih, bukan manis
        (r'\bkecap\s+asin\b',        0.9),
        (r'\bkecap\s+ikan\b',        0.9),
        (r'\bkecap\s+inggris\b',     0.8),   # Worcestershire-like (146x)
        # Saus tiram (1.085x) — umami tinggi
        (r'\bsaus\s+tiram\b',        1.0),
        # Tauco / taosi
        (r'\btauco\b',               0.8),
        (r'\btaosi\b',               0.8),
        # Ebi / udang kering
        (r'\bebi\b',                 0.7),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # ASAM  →  naikkan takaran bahan pembawa rasa asam
    # ══════════════════════════════════════════════════════════════════════════
    'sour': [
        # Jeruk nipis & kerabatnya (1.305 + 163 + 87 + 76 + 39 ... entri)
        (r'\bjeruk\s+nipis\b',       1.0),
        (r'\bjeruk\s+limau\b',       1.0),
        (r'\bjeruk\s+lemon\b',       1.0),
        (r'\bjeruk\s+purut\b',       0.8),   # lebih ke aroma, sedikit asam
        (r'\bjeruk\s+limo\b',        1.0),
        (r'\bnipis\b',               0.9),   # standalone (21x)
        (r'\blimau\b',               0.9),   # standalone (12x)
        (r'\blemon\b',               0.9),
        (r'\blime\b',                0.9),
        # Cuka (177x + 3x)
        (r'\bcuka\b',                1.0),
        (r'\bvinegar\b',             1.0),
        # Asam jawa dan kerabatnya (598 + 91 + 59 + 36 + 20 ... entri)
        (r'\basam\s+jawa\b',         1.0),
        (r'\basem\s+jawa?\b',        1.0),   # asem jawa (59x)
        (r'\basam\s+kandis\b',       1.0),   # (91x)
        (r'\basam\s+sunti\b',        1.0),   # (20x)
        (r'\basam\s+gelugur\b',      1.0),   # (6x)
        (r'\basem\b(?!\s+manis)',     0.8),   # asem standalone (36x) kecuali asem manis
        # "asam" standalone — hati-hati false positive (asam lemak, amino, urat)
        (r'\basam\b(?!\s+(lemak|amino|urat|folat|lambung|lambungan|asetat))',
                                     0.7),
        # Tomat (4.874 + 26 entri) — asam ringan
        (r'\btomat\b',               0.6),
        (r'\btomato\b',              0.6),
        # Belimbing wuluh (84 + 24 + 23 entri)
        (r'\bbelimbing\s+wuluh\b',   1.0),
        (r'\bbelimbing\s+sayur\b',   1.0),
        (r'\bwuluh\b',               0.9),   # standalone (24x)
        # Saus tomat (371x) — asam ringan
        (r'\bsaus\s+tomat\b',        0.5),
        (r'\bsaos\s+tomat\b',        0.5),
        # Tamarind
        (r'\btamarind\b',            1.0),
        # Nanas (kadang dipakai untuk asam di masakan)
        (r'\bnanas\b',               0.4),
    ],
}

# Pre-compile semua regex untuk performa
_COMPILED = {
    flavor: [(re.compile(pat, re.IGNORECASE), weight) for pat, weight in kws]
    for flavor, kws in FLAVOR_KEYWORDS.items()
}


# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_flavor_profile(user_id: int) -> dict:
    conn = get_db()
    row  = conn.execute(
        'SELECT * FROM flavor_profile WHERE user_id=%s', (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return {
            'spicy_level' : row['spicy_level'],
            'sweet_level' : row['sweet_level'],
            'savory_level': row['savory_level'],
            'sour_level'  : row['sour_level'],
            'servings'    : row['servings'],
        }
    return {
        'spicy_level': 0, 'sweet_level': 0,
        'savory_level': 0, 'sour_level': 0,
        'servings': DEFAULT_SERVINGS,
    }


def save_flavor_profile(user_id: int, profile: dict):
    conn = get_db()
    conn.execute(
        '''INSERT INTO flavor_profile
               (user_id, spicy_level, sweet_level, savory_level, sour_level, servings)
           VALUES (%s,%s,%s,%s,%s,%s)
           ON CONFLICT(user_id) DO UPDATE SET
               spicy_level=excluded.spicy_level,
               sweet_level=excluded.sweet_level,
               savory_level=excluded.savory_level,
               sour_level=excluded.sour_level,
               servings=excluded.servings''',
        (
            user_id,
            max(0, min(5, int(profile.get('spicy_level',  0)))),
            max(0, min(5, int(profile.get('sweet_level',  0)))),
            max(0, min(5, int(profile.get('savory_level', 0)))),
            max(0, min(5, int(profile.get('sour_level',   0)))),
            max(1, min(20, int(profile.get('servings', DEFAULT_SERVINGS)))),
        )
    )
    conn.commit()
    conn.close()


# ── Core matching logic ────────────────────────────────────────────────────────

def _get_flavor_factor(ingredient_lower: str, profile: dict) -> tuple[float, list[str]]:
    """
    Hitung faktor pengali rasa untuk satu bahan.

    Algoritma:
    1. Cek setiap flavor yang levelnya > 0
    2. Untuk setiap flavor, cek semua pattern keyword (pre-compiled)
    3. Ambil bobot tertinggi yang match (tidak dijumlah, agar tidak double-count)
    4. Faktor akhir = 1.0 + sum(level × 0.10 × best_weight per flavor)

    Return: (factor: float, matched_flavors: list[str])
    """
    factor       = 1.0
    matched      = []

    flavor_levels = {
        'spicy' : profile.get('spicy_level',  0),
        'sweet' : profile.get('sweet_level',  0),
        'savory': profile.get('savory_level', 0),
        'sour'  : profile.get('sour_level',   0),
    }

    for flavor, level in flavor_levels.items():
        if level == 0:
            continue

        best_weight = 0.0
        for compiled_pat, weight in _COMPILED[flavor]:
            if compiled_pat.search(ingredient_lower):
                best_weight = max(best_weight, weight)

        if best_weight > 0:
            increment = level * 0.10 * best_weight   # maks +50% di level 5 bobot 1.0
            factor   += increment
            matched.append(flavor)

    return round(factor, 4), matched


def _parse_amount(text: str):
    """
    Cari angka dan satuan pertama dalam teks bahan.
    Return (angka: float, satuan: str, sisa_teks: str) atau (None, None, text).
    """
    m = UNIT_PATTERN.search(text)
    if m and m.group(1):
        raw = m.group(1).replace(',', '.').replace('/', '÷')
        try:
            if '÷' in raw:
                a, b = raw.split('÷')
                num = float(a) / float(b)
            else:
                num = float(raw)
        except ValueError:
            return None, None, text

        unit = (m.group(2) or '').strip()
        rest = (text[:m.start()] + text[m.end():]).strip()
        return num, unit, rest
    return None, None, text


def _fmt(n: float) -> str:
    """Format angka: integer kalau bulat, 1 desimal kalau tidak."""
    return str(int(n)) if n == int(n) else f'{n:.1f}'


# ── Public API ─────────────────────────────────────────────────────────────────

def adjust_ingredients(ingredients: list[str], profile: dict) -> list[dict]:
    """
    Terima list bahan mentah (dari dataset), kembalikan list dict:
      {
        'original' : teks asli,
        'adjusted' : teks setelah disesuaikan,
        'modified' : bool,
        'note'     : keterangan singkat perubahan,
      }

    Dua tahap penyesuaian:
      1. Scale porsi   → ×(target / DEFAULT_SERVINGS)
      2. Scale rasa    → ×flavor_factor (hanya bahan yang match keyword rasa)
    """
    FLAVOR_LABEL = {
        'spicy' : 'pedas',
        'sweet' : 'manis',
        'savory': 'gurih',
        'sour'  : 'asam',
    }

    target = max(1, int(profile.get('servings', DEFAULT_SERVINGS)))
    scale  = target / DEFAULT_SERVINGS
    result = []

    for ing in ingredients:
        num, unit, rest = _parse_amount(ing)

        if num is None:
            # Tidak ada angka ("secukupnya", "sesuai selera", dll.)
            # Tetap match rasa untuk catatan, tapi tidak bisa diubah angkanya
            ing_lower          = ing.lower()
            ff, matched_flavors = _get_flavor_factor(ing_lower, profile)
            note_parts = []
            if matched_flavors:
                labels = '+'.join(FLAVOR_LABEL[f] for f in matched_flavors)
                note_parts.append(f'tambah {labels} sesuai selera')
            result.append({
                'original': ing,
                'adjusted': ing,
                'modified': False,
                'note'    : ', '.join(note_parts),
            })
            continue

        ing_lower          = ing.lower()
        ff, matched_flavors = _get_flavor_factor(ing_lower, profile)

        new_num = num * scale * ff
        new_num = round(new_num * 4) / 4   # bulatkan ke 0.25 terdekat

        if unit:
            adjusted_text = f'{_fmt(new_num)} {unit} {rest}'.strip()
        else:
            adjusted_text = f'{_fmt(new_num)} {rest}'.strip()

        # Susun catatan
        note_parts = []
        if target != DEFAULT_SERVINGS:
            note_parts.append(f'{target} porsi')
        if matched_flavors:
            labels = '+'.join(FLAVOR_LABEL[f] for f in matched_flavors)
            pct    = round((ff - 1.0) * 100)
            note_parts.append(f'+{pct}% {labels}')

        result.append({
            'original': ing,
            'adjusted': adjusted_text,
            'modified': (round(new_num, 2) != round(num, 2)),
            'note'    : ', '.join(note_parts),
        })

    return result


# ── Debug helper (opsional, untuk testing) ────────────────────────────────────

def debug_ingredient(text: str, profile: dict) -> dict:
    """
    Tampilkan detail matching untuk satu bahan.
    Pakai di Python shell: from models.flavor import debug_ingredient
    """
    num, unit, rest = _parse_amount(text)
    ff, matched     = _get_flavor_factor(text.lower(), profile)
    return {
        'input'  : text,
        'parsed' : {'num': num, 'unit': unit, 'rest': rest},
        'factor' : ff,
        'matched': matched,
    }

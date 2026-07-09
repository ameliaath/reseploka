"""
routes/api.py
─────────────
Blueprint untuk semua endpoint AJAX / JSON API.
Semua route di sini diawali dengan /api/
"""
import io, re
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user

from ml_engine        import df, CATEGORY_IMAGES
from models.favorite  import toggle_favorite
from models.note      import add_note, delete_note, save_checklist, get_notes, get_checklist
from models.rating    import set_rating, save_preferences, get_ratings
from models.flavor    import get_flavor_profile, save_flavor_profile, adjust_ingredients

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ── Favorit ───────────────────────────────────────────────────────────────────
@api_bp.route('/favorite', methods=['POST'])
@login_required
def favorite():
    recipe_id = request.json.get('recipe_id')
    is_fav, count = toggle_favorite(current_user.id, recipe_id)
    return jsonify({'is_favorite': is_fav, 'count': count})


# ── Catatan ───────────────────────────────────────────────────────────────────
@api_bp.route('/note', methods=['POST'])
@login_required
def note_add():
    data      = request.json
    recipe_id = data.get('recipe_id')
    text      = data.get('note', '').strip()
    if not text:
        return jsonify({'success': False, 'message': 'Catatan tidak boleh kosong'})
    notes = add_note(current_user.id, recipe_id, text)
    return jsonify({'success': True, 'notes': notes})


@api_bp.route('/note/delete', methods=['POST'])
@login_required
def note_delete():
    note_id = request.json.get('note_idx')
    delete_note(current_user.id, note_id)
    return jsonify({'success': True})


# ── Checklist ─────────────────────────────────────────────────────────────────
@api_bp.route('/checklist', methods=['POST'])
@login_required
def checklist():
    data      = request.json
    recipe_id = data.get('recipe_id')
    items     = data.get('items', [])
    save_checklist(current_user.id, recipe_id, items)
    return jsonify({'success': True})


# ── Rating ────────────────────────────────────────────────────────────────────
@api_bp.route('/rating', methods=['POST'])
@login_required
def rating():
    data      = request.json
    recipe_id = data.get('recipe_id')
    stars     = int(data.get('stars', 0))
    try:
        stars, total_rated, avg = set_rating(current_user.id, recipe_id, stars)
        return jsonify({'success': True, 'stars': stars, 'total_rated': total_rated, 'avg': avg})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400


# ── Preferensi diet ───────────────────────────────────────────────────────────
@api_bp.route('/preferensi', methods=['POST'])
@login_required
def preferensi():
    save_preferences(current_user.id, request.json)
    return jsonify({'success': True})


# ── Profil rasa & takaran ─────────────────────────────────────────────────────
@api_bp.route('/flavor-profile', methods=['GET'])
@login_required
def flavor_profile_get():
    return jsonify(get_flavor_profile(current_user.id))


@api_bp.route('/flavor-profile', methods=['POST'])
@login_required
def flavor_profile_save():
    # Merge dengan data tersimpan agar field yg tidak dikirim tidak di-reset ke 0
    # Contoh: halaman rasa.html tidak kirim 'servings', jadi servings harus dipertahankan
    data     = dict(request.json or {})
    existing = get_flavor_profile(current_user.id)
    for key in ('spicy_level', 'sweet_level', 'savory_level', 'sour_level', 'servings'):
        if key not in data:
            data[key] = existing.get(key, 0 if key != 'servings' else 2)
    save_flavor_profile(current_user.id, data)
    return jsonify({'success': True})


@api_bp.route('/adjust-ingredients/<int:recipe_id>', methods=['GET'])
@login_required
def adjust_ingredients_api(recipe_id):
    """
    Kembalikan bahan yang sudah disesuaikan berdasarkan profil rasa + porsi.
    Query param opsional: ?servings=N untuk override sementara.
    """
    if recipe_id < 0 or recipe_id >= len(df):
        return jsonify({'error': 'Resep tidak ditemukan'}), 404

    row         = df.iloc[recipe_id]
    ingredients = [i.strip() for i in str(row['Ingredients']).split('--') if i.strip()]
    profile     = get_flavor_profile(current_user.id)

    override = request.args.get('servings')
    if override and override.isdigit():
        profile['servings'] = int(override)

    adjusted = adjust_ingredients(ingredients, profile)
    return jsonify({
        'recipe_id'   : recipe_id,
        'recipe_title': row['Title'],
        'servings'    : profile['servings'],
        'ingredients' : adjusted,
    })


# ── Export PDF lengkap ────────────────────────────────────────────────────────
@api_bp.route('/export-pdf/<int:recipe_id>')
@login_required
def export_pdf(recipe_id):
    if recipe_id < 0 or recipe_id >= len(df):
        return 'Not found', 404

    row = df.iloc[recipe_id]
    uid = current_user.id

    profile     = get_flavor_profile(uid)

    # Porsi: prioritaskan query param ?servings=N (dikirim dari tombol +/− di halaman resep)
    # Kalau tidak ada, fallback ke porsi tersimpan di profil user
    qs_servings = request.args.get('servings')
    if qs_servings and qs_servings.isdigit():
        servings = max(1, min(20, int(qs_servings)))
        profile  = dict(profile)           # copy agar tidak mutasi object asli
        profile['servings'] = servings
    else:
        servings = profile.get('servings', 2)

    raw_ings    = [i.strip() for i in str(row['Ingredients']).split('--') if i.strip()]
    adjusted    = adjust_ingredients(raw_ings, profile)
    steps       = [s.strip() for s in str(row['Steps']).split('--') if s.strip()]
    notes       = get_notes(uid, recipe_id)
    cl_items    = get_checklist(uid, recipe_id)
    ratings     = get_ratings(uid)
    user_rating = ratings.get(str(recipe_id), 0)

    try:
        import html as htmllib
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles    import ParagraphStyle
        from reportlab.lib.units     import cm
        from reportlab.lib           import colors
        from reportlab.platypus      import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.enums     import TA_CENTER

        def ct(text):
            text = htmllib.unescape(str(text))
            text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', text)
            return text.replace('<', '').replace('>', '').strip()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                 leftMargin=2.2*cm, rightMargin=2.2*cm,
                                 topMargin=2.2*cm, bottomMargin=2.2*cm)

        PINK  = colors.HexColor('#db2777')
        LPINK = colors.HexColor('#fce7f3')
        DARK  = colors.HexColor('#2d1a22')
        GRAY  = colors.HexColor('#7a4e5e')
        GREEN = colors.HexColor('#059669')
        BLUE  = colors.HexColor('#2563eb')

        def ps(name, **kw):
            defaults = dict(fontName='Helvetica', fontSize=10, textColor=DARK, spaceAfter=4, leading=16)
            defaults.update(kw)
            return ParagraphStyle(name, **defaults)

        title_s  = ps('T',  fontName='Helvetica-Bold', fontSize=22, textColor=PINK, spaceAfter=4,  alignment=TA_CENTER, leading=28)
        sub_s    = ps('S',  textColor=GRAY, spaceAfter=10, alignment=TA_CENTER)
        head_s   = ps('H',  fontName='Helvetica-Bold', fontSize=13, textColor=PINK, spaceBefore=14, spaceAfter=8)
        body_s   = ps('B',  leftIndent=10)
        body_mod = ps('BM', fontName='Helvetica-Bold', textColor=GREEN, leftIndent=10)
        step_s   = ps('ST', spaceAfter=8, leading=17, leftIndent=20)
        note_s   = ps('N',  textColor=BLUE, leftIndent=10)
        small_s  = ps('SM', fontSize=8, textColor=GRAY, leftIndent=10)
        foot_s   = ps('F',  fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceBefore=14)

        stars_str = ('★' * user_rating + '☆' * (5 - user_rating)) if user_rating else 'Belum dinilai'

        # Foto resep dari kolom Photo di dataset — kalau resep tidak punya foto
        # sendiri, pakai foto kategori sebagai cadangan (sama seperti di
        # halaman pencarian & kategori), supaya PDF tidak pernah kosong fotonya.
        photo_url = str(row.get('Photo', '') or CATEGORY_IMAGES.get(row['Category'], '') or '').strip()

        # Elemen foto (kalau ada)
        photo_elements = []
        if photo_url:
            try:
                import urllib.request as _ur
                from reportlab.platypus import Image as RLImage
                from reportlab.lib.units import cm as _cm
                _req = _ur.Request(photo_url, headers={'User-Agent': 'Mozilla/5.0'})
                _resp = _ur.urlopen(_req, timeout=8)
                _img_data = _resp.read()
                _img_buf = io.BytesIO(_img_data)
                # Foto dibuat lebih kecil (tidak selebar halaman) agar tidak mendominasi
                _img_w = 8.5*_cm
                _img_h = _img_w * 9 / 16   # rasio 16:9
                _rl_img = RLImage(_img_buf, width=_img_w, height=_img_h)
                _rl_img.hAlign = 'CENTER'
                photo_elements = [Spacer(1, 0.4*_cm), _rl_img, Spacer(1, 0.2*_cm)]
            except Exception:
                photo_elements = []  # Gagal load foto → skip, PDF tetap dibuat

        story = [
            Spacer(1, 0.2*cm),
            Paragraph(ct(row['Title']), title_s),
            Paragraph(
                f"Kategori: {row['Category'].capitalize()}  ·  "
                f"{int(row['Loves'])} likes  ·  {servings} porsi  ·  Rating: {stars_str}",
                sub_s
            ),
            HRFlowable(width='100%', thickness=2, color=PINK, spaceAfter=10),
            *photo_elements,
        ]

        # Bahan
        has_mod = any(a['modified'] for a in adjusted)
        story.append(Paragraph(f'Bahan-bahan — {servings} Porsi', head_s))
        if has_mod:
            story.append(Paragraph(
                '<i>* Bahan bertanda ✦ telah disesuaikan dengan preferensi rasa dan porsi kamu.</i>',
                small_s
            ))
        for a in adjusted:
            if a['modified']:
                note = f'  <font size="8" color="#059669">({ct(a["note"])})</font>' if a['note'] else ''
                story.append(Paragraph(f'✦  {ct(a["adjusted"])}{note}', body_mod))
            else:
                story.append(Paragraph(f'•  {ct(a["adjusted"])}', body_s))

        # Daftar belanja
        if cl_items:
            story += [
                Spacer(1, 0.3*cm),
                HRFlowable(width='100%', thickness=1, color=LPINK, spaceAfter=6),
                Paragraph('Daftar Belanja Saya', head_s),
            ]
            for item in cl_items:
                checked = '☑' if item.get('checked') else '☐'
                sty = ps(f'CK{id(item)}', textColor=GRAY if item.get('checked') else DARK, leftIndent=10)
                story.append(Paragraph(f'{checked}  {ct(item.get("text",""))}', sty))

        # Cara memasak
        story += [
            Spacer(1, 0.3*cm),
            HRFlowable(width='100%', thickness=1, color=LPINK, spaceAfter=6),
            Paragraph('Cara Memasak', head_s),
        ]
        for i, step in enumerate(steps, 1):
            story.append(Paragraph(f'<b>{i}.</b>  {ct(step)}', step_s))

        # Catatan user
        if notes:
            story += [
                Spacer(1, 0.3*cm),
                HRFlowable(width='100%', thickness=1, color=LPINK, spaceAfter=6),
                Paragraph('Catatan Saya', head_s),
            ]
            for note in notes:
                story.append(Paragraph(f'📌  {ct(note["text"])}', note_s))

        story += [
            Spacer(1, 0.4*cm),
            HRFlowable(width='100%', thickness=1, color=LPINK),
            Paragraph(
                f'Diekspor dari ResepLoka — {datetime.now().strftime("%d %B %Y")}  |  User: {current_user.username}',
                foot_s
            ),
        ]

        doc.build(story)
        buf.seek(0)
        safe = re.sub(r'[^\w\s-]', '', row['Title'])[:50].strip()
        return send_file(buf, as_attachment=True,
                         download_name=f'Resep_{safe}.pdf',
                         mimetype='application/pdf')

    except Exception as e:
        return jsonify({'error': str(e)}), 500

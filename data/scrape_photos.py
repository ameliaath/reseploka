"""
scrape_photos.py
────────────────
Script untuk mengisi kolom 'Photo' di dataset-gabungan-clean.csv
dengan URL foto asli dari Cookpad.

Cara pakai:
  1. pip install requests beautifulsoup4
  2. Taruh file ini di folder yang sama dengan dataset-gabungan-clean.csv
  3. python scrape_photos.py

Script akan:
  - Baca dataset CSV yang ada
  - Untuk setiap resep yang punya URL Cookpad, scrape URL fotonya
  - Simpan progress ke 'photo_cache.csv' (bisa dilanjutkan kalau terputus)
  - Hasil akhir disimpan ke 'dataset-gabungan-clean.csv' (backup dibuat otomatis)

Estimasi waktu: ~4-5 jam untuk 15.000 resep (ada delay 1 detik per request
agar tidak di-ban Cookpad). Bisa dijalankan bertahap — tinggal Ctrl+C,
lanjutkan lagi nanti, progress tidak hilang.
"""

import os
import time
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup

# ── Konfigurasi ───────────────────────────────────────────────────────────────
BASE_URL    = 'https://cookpad.com'
CSV_PATH    = 'dataset-gabungan-clean.csv'
CACHE_PATH  = 'photo_cache.csv'
BACKUP_PATH = 'dataset-gabungan-clean.BACKUP.csv'
DELAY_MIN   = 1.0   # detik minimum antar request
DELAY_MAX   = 2.5   # detik maksimum antar request
BATCH_SAVE  = 50    # simpan cache setiap N resep

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://cookpad.com/id',
}

# ── Fungsi scrape satu URL ────────────────────────────────────────────────────

def get_photo_url(recipe_url_path: str) -> str:
    """
    Ambil URL foto utama dari halaman resep Cookpad.
    Return string URL foto, atau '' kalau gagal.
    """
    if not recipe_url_path or pd.isna(recipe_url_path):
        return ''

    full_url = BASE_URL + str(recipe_url_path)
    try:
        resp = requests.get(full_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return ''

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Cari dari og:image (paling reliable)
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            url = og['content'].strip()
            if 'cpcdn.com' in url or 'cookpad' in url:
                return url

        # Fallback: cari dari tag img dengan class foto utama
        for img in soup.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if 'cpcdn.com/recipes' in src:
                return src.strip()

        return ''

    except Exception:
        return ''


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== ResepLoka Photo Scraper ===\n")

    # Load dataset
    print(f"Loading dataset: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    print(f"Total resep: {len(df)}")

    # Buat backup sekali
    if not os.path.exists(BACKUP_PATH):
        df.to_csv(BACKUP_PATH, index=False)
        print(f"Backup dibuat: {BACKUP_PATH}")

    # Pastikan kolom Photo ada
    if 'Photo' not in df.columns:
        df['Photo'] = ''
    df['Photo'] = df['Photo'].fillna('')

    # Load cache kalau ada (untuk resume)
    cache = {}
    if os.path.exists(CACHE_PATH):
        cache_df = pd.read_csv(CACHE_PATH)
        cache = dict(zip(cache_df['url_path'], cache_df['photo']))
        print(f"Cache dimuat: {len(cache)} entri\n")

    # Hitung yang belum diproses
    todo = df[
        df['URL'].notna() &
        (df['URL'] != '') &
        (df['Photo'] == '')
    ]
    print(f"Resep yang perlu di-scrape: {len(todo)}")
    print(f"Sudah ada foto          : {(df['Photo'] != '').sum()}")
    print(f"\nMulai scraping... (Ctrl+C untuk pause, bisa dilanjutkan)\n")

    processed = 0
    success   = 0
    cache_updates = {}

    try:
        for idx, row in todo.iterrows():
            url_path = str(row['URL'])

            # Cek cache dulu
            if url_path in cache:
                photo = cache[url_path]
            else:
                photo = get_photo_url(url_path)
                cache_updates[url_path] = photo
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            df.at[idx, 'Photo'] = photo
            processed += 1
            if photo:
                success += 1

            # Progress
            if processed % 10 == 0:
                pct = processed / len(todo) * 100
                print(f"  [{processed}/{len(todo)}] {pct:.1f}% — "
                      f"berhasil: {success} | "
                      f"resep: {row['Title'][:40]}")

            # Simpan cache & CSV berkala
            if processed % BATCH_SAVE == 0:
                _save_cache(cache_updates, cache)
                df.to_csv(CSV_PATH, index=False)
                print(f"  💾 Progress disimpan ({processed} resep)")

    except KeyboardInterrupt:
        print("\n\n⏸️  Dihentikan oleh user — menyimpan progress...")

    finally:
        # Simpan hasil akhir
        _save_cache(cache_updates, cache)
        df.to_csv(CSV_PATH, index=False)
        total_photos = (df['Photo'] != '').sum()
        print(f"\n✅ Selesai! {total_photos}/{len(df)} resep sudah punya foto.")
        print(f"   Dataset disimpan ke: {CSV_PATH}")


def _save_cache(new_entries: dict, existing: dict):
    """Simpan cache ke file CSV."""
    existing.update(new_entries)
    cache_df = pd.DataFrame([
        {'url_path': k, 'photo': v}
        for k, v in existing.items()
    ])
    cache_df.to_csv(CACHE_PATH, index=False)


if __name__ == '__main__':
    main()

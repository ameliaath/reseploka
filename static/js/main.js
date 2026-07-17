/* ══════════════════════════════════════════════════════════
   ResepLoka — Main JS
══════════════════════════════════════════════════════════ */

// ── Theme Manager ──────────────────────────────────────────────────────────
const ThemeManager = {
  STORAGE_KEY: 'rasanusa_theme',

  get() {
    return localStorage.getItem(this.STORAGE_KEY) || 'auto';
  },

  set(mode) {
    localStorage.setItem(this.STORAGE_KEY, mode);
    this.apply(mode);
    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.theme === mode);
    });
  },

  apply(mode) {
    const html = document.documentElement;
    if (mode === 'light') {
      html.setAttribute('data-theme', 'light');
    } else if (mode === 'dark') {
      html.setAttribute('data-theme', 'dark');
    } else {
      // auto: siang = light, malam = dark
      const hour = new Date().getHours();
      const isDaytime = hour >= 6 && hour < 18;
      html.setAttribute('data-theme', isDaytime ? 'light' : 'dark');
    }
  },

  init() {
    const saved = this.get();
    this.apply(saved);

    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.theme === saved);
      btn.addEventListener('click', () => this.set(btn.dataset.theme));
    });

    // Re-apply auto every minute
    if (saved === 'auto') {
      setInterval(() => { if (this.get() === 'auto') this.apply('auto'); }, 60000);
    }
  }
};


// ── Navbar scroll shadow ───────────────────────────────────────────────────
function initNavScroll() {
  const nav = document.getElementById('mainNav');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 20);
  }, { passive: true });
}

// ── Navbar mobile menu fix ───────────────────────────────────────────────
// Fallback untuk :has() di Safari versi lama: tambah/hapus class 'menu-open'
// di #mainNav setiap kali menu mobile dibuka/ditutup, supaya backdrop-filter
// dimatikan dan background jadi solid (mencegah bug rendering "ngambang"
// pada kombinasi position:sticky + backdrop-filter di Safari iOS).
function initNavCollapseFix() {
  const nav        = document.getElementById('mainNav');
  const navMenu    = document.getElementById('navMenu');
  const toggler    = document.querySelector('.navbar-toggler');
  if (!nav || !navMenu) return;
  navMenu.addEventListener('show.bs.collapse', () => nav.classList.add('menu-open'));
  navMenu.addEventListener('hide.bs.collapse', () => nav.classList.remove('menu-open'));

  // Klik di luar kotak menu (atau di luar tombol garis tiga) → otomatis nutup menu mobile
  document.addEventListener('click', (e) => {
    const isOpen = navMenu.classList.contains('show');
    if (!isOpen) return;
    const clickedInsideMenu = navMenu.contains(e.target);
    const clickedToggler = toggler?.contains(e.target);
    if (!clickedInsideMenu && !clickedToggler) {
      bootstrap.Collapse.getOrCreateInstance(navMenu).hide();
    }
  });
}

// ── Page animation ────────────────────────────────────────────────────────
function initPageAnimation() {
  document.querySelector('main')?.classList.add('page-enter');
}

// ── Search logic (index page) ─────────────────────────────────────────────
const SearchManager = {
  currentQuery: '',
  currentSort: '',
  currentPage: 1,
  perPage: 20,
  totalResults: 0,
  shownCount: 0,
  loading: false,

  init() {
    const box = document.getElementById('searchBox');
    if (!box) return;

    const clearBtn = document.getElementById('searchClearBtn');
    const toggleClearBtn = () => {
      if (!clearBtn) return;
      clearBtn.style.display = box.value.length > 0 ? 'flex' : 'none';
    };
    toggleClearBtn();

    // Show/hide clear (x) button as user types
    box.addEventListener('input', toggleClearBtn);

    // Clear button: kosongkan kolom & sembunyikan hasil pencarian
    clearBtn?.addEventListener('click', () => {
      box.value = '';
      toggleClearBtn();
      box.focus();
      this.clearSearch();
    });

    // Enter key
    box.addEventListener('keydown', e => {
      if (e.key === 'Enter') this.doSearch(box.value.trim());
    });

    // Search button
    document.getElementById('searchBtn')?.addEventListener('click', () => {
      this.doSearch(box.value.trim());
    });

    // Hint tags
    document.querySelectorAll('.hint-tag').forEach(tag => {
      tag.addEventListener('click', () => {
        box.value = tag.dataset.ingredient;
        this.doSearch(tag.dataset.ingredient);
      });
    });

    // Sort buttons
    document.querySelectorAll('.sort-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.currentSort = btn.dataset.sort;
        document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.doSearch(this.currentQuery);
      });
    });

    // Load more button
    document.getElementById('loadMoreBtn')?.addEventListener('click', () => {
      this.loadMore();
    });

    // URL params
    const params = new URLSearchParams(window.location.search);
    const q = params.get('q');
    if (q) {
      box.value = q;
      this.doSearch(q);
    }
    toggleClearBtn();

    // Fix bug: pas balik ke halaman ini (baik lewat gesture swipe iOS, tombol
    // back, maupun reload dari cache), kolom pencarian kadang gak sinkron
    // dengan hasil yang tampil — ada kasus browser ngosongin isi <input>
    // sementara hasil resep di bawahnya masih hasil pencarian sebelumnya
    // (dipulihkan apa adanya dari cache). Setiap kali halaman "muncul" lagi,
    // paksa sinkronkan ulang kolom & hasil pencarian dengan parameter "q"
    // yang ada di URL, supaya keduanya selalu konsisten satu sama lain.
    window.addEventListener('pageshow', () => {
      const p = new URLSearchParams(window.location.search);
      const qq = p.get('q');
      box.value = qq || '';
      toggleClearBtn();

      const panel = document.getElementById('searchResultsPanel');
      const list  = document.getElementById('searchResultsList');
      const panelHidden = !panel || panel.style.display === 'none';
      const listEmpty   = !list || list.children.length === 0;

      if (qq && (panelHidden || listEmpty)) {
        // Hasil belum/tidak tampil padahal ada query di URL → cari ulang
        this.doSearch(qq);
      } else if (!qq) {
        // Gak ada query sama sekali → pastikan panel hasil ikut disembunyikan
        this.clearSearch();
      }
    });
  },

  updateCountLabel() {
    const countEl = document.getElementById('resultCount');
    if (!countEl) return;
    if (this.totalResults === 0) {
      countEl.textContent = '';
    } else if (this.shownCount >= this.totalResults) {
      countEl.textContent = `Menampilkan semua ${this.totalResults} resep yang cocok`;
    } else {
      countEl.textContent = `Menampilkan ${this.shownCount} dari ${this.totalResults} resep paling cocok`;
    }
  },

  updateLoadMoreVisibility() {
    const wrap = document.getElementById('loadMoreWrap');
    if (!wrap) return;
    wrap.style.display = this.shownCount < this.totalResults ? 'flex' : 'none';
  },

  clearSearch() {
    this.currentQuery = '';
    this.currentPage = 1;
    this.shownCount = 0;
    this.totalResults = 0;

    const panel = document.getElementById('searchResultsPanel');
    const list = document.getElementById('searchResultsList');
    const catSection = document.getElementById('categorySection');
    const loadMoreWrap = document.getElementById('loadMoreWrap');

    if (panel) panel.style.display = 'none';
    if (list) list.innerHTML = '';
    if (catSection) catSection.style.display = '';
    if (loadMoreWrap) loadMoreWrap.style.display = 'none';

    // Bersihkan parameter "q" dari URL tanpa reload halaman
    const url = new URL(window.location);
    url.searchParams.delete('q');
    window.history.replaceState({}, '', url);
  },

  async doSearch(query) {
    if (!query) return;
    this.currentQuery = query;
    this.currentPage = 1;
    this.shownCount = 0;

    const panel = document.getElementById('searchResultsPanel');
    const list = document.getElementById('searchResultsList');
    const catSection = document.getElementById('categorySection');
    const loadMoreWrap = document.getElementById('loadMoreWrap');

    if (panel) panel.style.display = 'block';
    if (catSection) catSection.style.display = 'none';
    if (loadMoreWrap) loadMoreWrap.style.display = 'none';

    if (list) list.innerHTML = '<div class="spinner-pink"></div>';

    // Update URL
    const url = new URL(window.location);
    url.searchParams.set('q', query);
    window.history.replaceState({}, '', url);

    try {
      const res = await fetch(`/search?q=${encodeURIComponent(query)}&sort=${this.currentSort}&page=${this.currentPage}`);
      const data = await res.json();

      this.totalResults = data.total || 0;
      this.perPage = data.per_page || this.perPage;

      if (!list) return;

      if (!data.results || data.results.length === 0) {
        this.shownCount = 0;
        this.updateCountLabel();
        list.innerHTML = `
          <div class="empty-state">
            <span class="emoji">🔍</span>
            <p>Tidak ada resep dengan bahan "<strong>${escapeHtml(query)}</strong>"</p>
            <p class="small">Coba kata lain, misalnya: ayam, bawang, santan</p>
          </div>`;
        return;
      }

      list.innerHTML = '';
      data.results.forEach((r, i) => {
        const card = this.buildCard(r, query, i);
        list.appendChild(card);
      });

      this.shownCount = data.results.length;
      this.updateCountLabel();
      this.updateLoadMoreVisibility();

    } catch (err) {
      if (list) list.innerHTML = '<p class="text-center text-danger mt-4">Terjadi kesalahan. Coba lagi.</p>';
    }
  },

  async loadMore() {
    if (this.loading || this.shownCount >= this.totalResults) return;
    this.loading = true;

    const btn = document.getElementById('loadMoreBtn');
    const list = document.getElementById('searchResultsList');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Memuat...';
    }

    try {
      this.currentPage += 1;
      const res = await fetch(`/search?q=${encodeURIComponent(this.currentQuery)}&sort=${this.currentSort}&page=${this.currentPage}`);
      const data = await res.json();

      this.totalResults = data.total || this.totalResults;

      if (list && data.results) {
        data.results.forEach((r, i) => {
          const card = this.buildCard(r, this.currentQuery, this.shownCount + i);
          list.appendChild(card);
        });
        this.shownCount += data.results.length;
      }

      this.updateCountLabel();
      this.updateLoadMoreVisibility();

    } catch (err) {
      this.currentPage -= 1; // rollback so a retry re-requests the same page
    } finally {
      this.loading = false;
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-down-circle"></i> Muat Resep Lainnya';
      }
    }
  },

  buildCard(recipe, query, idx) {
    const EMOJI = {
      ayam:'🍗', ikan:'🐟', kambing:'🥩', sapi:'🥩',
      tahu:'🟨', telur:'🍳', tempe:'🫘', udang:'🦐'
    };

    const div = document.createElement('a');
    div.className = 'recipe-card';
    div.href = `/recipe/${recipe.id}?from=search&q=${encodeURIComponent(query)}`;
    div.style.animationDelay = `${idx * 0.04}s`;
    div.style.animation = 'staggerFade 0.35s ease forwards';
    div.style.opacity = '0';

    const highlightedTitle = highlightText(recipe.title, query);
    const emoji      = EMOJI[recipe.category] || '🍽️';
    const finalPhoto = recipe.photo || '';

    div.innerHTML = `
      <div class="recipe-card-img-wrap">
        <img src="${finalPhoto}" alt="${recipe.title}"
             loading="lazy"
             style="${finalPhoto ? '' : 'display:none'}"
             onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
        <div class="recipe-card-img-placeholder"
             style="${finalPhoto ? 'display:none' : 'display:flex'}">${emoji}</div>
      </div>
      <div class="recipe-card-body">
        <div class="recipe-card-title">${highlightedTitle}</div>
        <div class="recipe-card-meta">
          <span><i class="bi bi-tag"></i> ${capitalize(recipe.category)}</span>
          <span class="loves-badge"><i class="bi bi-heart-fill"></i> ${recipe.loves}</span>
        </div>
        <span class="recipe-card-badge-sim">
          <i class="bi bi-stars"></i> ${recipe.similarity}% cocok
        </span>
      </div>`;
    return div;
  }
};

// ── Highlight helper ──────────────────────────────────────────────────────
function highlightText(text, query) {
  if (!query) return escapeHtml(text);
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  let result = escapeHtml(text);
  terms.forEach(term => {
    const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
    result = result.replace(regex, '<mark class="bahan-highlight">$1</mark>');
  });
  return result;
}

function highlightIngredients(ingredients, query) {
  if (!query) return;
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  document.querySelectorAll('.ingredient-item').forEach(el => {
    let html = escapeHtml(el.dataset.raw || el.textContent);
    terms.forEach(term => {
      const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
      html = html.replace(regex, '<mark class="bahan-highlight">$1</mark>');
    });
    el.innerHTML = `<span class="ing-icon">✿</span> ${html}`;
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function capitalize(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : str;
}

// ── Favorite button ───────────────────────────────────────────────────────
function initFavoriteBtn() {
  const btn = document.getElementById('favBtn');
  if (!btn) return;
  const recipeId = parseInt(btn.dataset.recipeId);

  btn.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/favorite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipe_id: recipeId })
      });
      const data = await res.json();

      btn.classList.toggle('active', data.is_favorite);
      btn.querySelector('.fav-label').textContent = data.is_favorite ? 'Tersimpan' : 'Favorit';
      btn.querySelector('i').className = data.is_favorite ? 'bi bi-heart-fill' : 'bi bi-heart';

      // Update navbar badge
      const badge = document.getElementById('navFavCount');
      if (badge) badge.textContent = data.count;

      // Pulse animation
      btn.style.transform = 'scale(1.15)';
      setTimeout(() => btn.style.transform = '', 300);
    } catch {}
  });
}

// ── Pelacak proses simpan yang masih berjalan (checklist & catatan) ─────────
// Dipakai supaya tombol "Unduh PDF" bisa menunggu proses simpan selesai dulu,
// mencegah data checklist/catatan belum masuk ke database saat PDF dibuat
// (terutama di koneksi mobile yang lebih lambat dari laptop/WiFi).
window.__pendingSaves = [];
function trackSave(promise) {
  window.__pendingSaves.push(promise);
  const clear = () => {
    window.__pendingSaves = window.__pendingSaves.filter(p => p !== promise);
  };
  promise.then(clear, clear);
  return promise;
}
window.flushPendingSaves = () => Promise.all(window.__pendingSaves).catch(() => {});

// ── Checklist ─────────────────────────────────────────────────────────────
function initChecklist() {
  const container = document.getElementById('checklistContainer');
  if (!container) return;
  const recipeId = container.dataset.recipeId;

  // Add new item
  document.getElementById('addCheckBtn')?.addEventListener('click', () => {
    addCheckItem('', container, recipeId);
    saveChecklist(recipeId);
  });

  // Existing items have data loaded from server (Jinja)
  container.querySelectorAll('.checklist-item').forEach(item => {
    hookCheckItem(item, container, recipeId);
  });
}

function addCheckItem(text, container, recipeId) {
  const item = document.createElement('div');
  item.className = 'checklist-item';
  item.innerHTML = `
    <input type="checkbox" class="checklist-cb" ${text ? '' : ''}>
    <input type="text" class="checklist-input" placeholder="Tambah bahan..." value="${escapeHtml(text)}">
    <button class="del-note-btn" title="Hapus"><i class="bi bi-x"></i></button>`;
  container.appendChild(item);
  hookCheckItem(item, container, recipeId);
  item.querySelector('.checklist-input')?.focus();
}

function hookCheckItem(item, container, recipeId) {
  const cb = item.querySelector('.checklist-cb');
  const input = item.querySelector('.checklist-input');
  const delBtn = item.querySelector('.del-note-btn');

  cb?.addEventListener('change', () => saveChecklist(recipeId));
  input?.addEventListener('input', () => saveChecklist(recipeId));
  delBtn?.addEventListener('click', () => {
    item.style.animation = 'none';
    item.style.opacity = '0';
    item.style.transform = 'translateX(-10px)';
    item.style.transition = 'all 0.2s';
    setTimeout(() => { item.remove(); saveChecklist(recipeId); }, 200);
  });
}

async function saveChecklist(recipeId) {
  const container = document.getElementById('checklistContainer');
  if (!container) return;
  const items = [];
  container.querySelectorAll('.checklist-item').forEach(item => {
    const cb = item.querySelector('.checklist-cb');
    const input = item.querySelector('.checklist-input');
    items.push({ text: input?.value || '', checked: cb?.checked || false });
  });
  await trackSave(fetch('/api/checklist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ recipe_id: recipeId, items })
  }));
}

// ── Notes ─────────────────────────────────────────────────────────────────
function initNotes() {
  const recipeId = document.getElementById('notesContainer')?.dataset.recipeId;
  if (!recipeId) return;

  document.getElementById('addNoteBtn')?.addEventListener('click', () => submitNote(recipeId));
  document.getElementById('noteInput')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitNote(recipeId); }
  });

  // Delete existing notes
  hookNoteDeletes(recipeId);
}

async function submitNote(recipeId) {
  const input = document.getElementById('noteInput');
  const text = input?.value.trim();
  if (!text) return;

  try {
    const res = await trackSave(fetch('/api/note', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipe_id: recipeId, note: text })
    }));
    const data = await res.json();
    if (data.success) {
      input.value = '';
      renderNotes(data.notes, recipeId);
    }
  } catch {}
}

async function deleteNote(recipeId, idx) {
  try {
    const res = await fetch('/api/note/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipe_id: recipeId, note_idx: idx })
    });
    const data = await res.json();
    if (data.success) location.reload();
  } catch {}
}

function hookNoteDeletes(recipeId) {
  document.querySelectorAll('.del-note-btn[data-note-idx]').forEach(btn => {
    btn.addEventListener('click', () => deleteNote(recipeId, parseInt(btn.dataset.noteIdx)));
  });
}

function renderNotes(notes, recipeId) {
  const container = document.getElementById('notesContainer');
  if (!container) return;
  container.innerHTML = '';
  notes.forEach((note, i) => {
    const div = document.createElement('div');
    div.className = 'note-item';
    div.innerHTML = `
      <span class="note-text">${escapeHtml(note.text)}</span>
      <button class="del-note-btn" data-note-idx="${i}" title="Hapus"><i class="bi bi-x-circle"></i></button>`;
    container.appendChild(div);
  });
  hookNoteDeletes(recipeId);
}

// ── Ingredient highlight from URL param ──────────────────────────────────
function initIngredientHighlight() {
  const params = new URLSearchParams(window.location.search);
  const q = params.get('q') || document.referrer;

  // Try to get search query from referrer
  let query = params.get('q') || '';
  if (!query) {
    try {
      const ref = new URL(document.referrer);
      query = ref.searchParams.get('q') || '';
    } catch {}
  }

  if (query) {
    // Store search query in sessionStorage
    sessionStorage.setItem('lastSearch', query);
  }

  const lastSearch = query || sessionStorage.getItem('lastSearch') || '';
  if (lastSearch) {
    highlightIngredients([], lastSearch);
  }
}

// ── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  initNavScroll();
  initNavCollapseFix();
  initPageAnimation();
  SearchManager.init();
  initFavoriteBtn();
  initChecklist();
  initNotes();
  initIngredientHighlight();
});

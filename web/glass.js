// Aurora glass: presentation layer for Luminaria.
// - keeps visual effects in step with Motion and PC capability
// - Library menu in the sidebar
// - the Lumen orb, which mirrors the assistant state published by core.js
// - permission chip in the top bar
// - background glow palettes (Settings > Appearance)
// - choice cards in place of a few dropdowns
// Reads the existing API only through the app's own api() helper.
(() => {
  const body = document.body;
  const root = document.documentElement;
  const store = {
    get(key) { try { return localStorage.getItem(key) || ''; } catch { return ''; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch {} }
  };

  /* ---------- Effects level and motion ---------- */
  const forced = store.get('luminaria-effects');
  const cores = navigator.hardwareConcurrency || 8;
  const memory = navigator.deviceMemory || 8;
  body.classList.toggle('effects-low', forced === 'low' || (forced !== 'full' && (cores <= 4 || memory <= 4)));
  window.addEventListener('studio-preferences', (event) => {
    body.classList.toggle('motion-off', (event.detail || {}).motion === false);
  });

  /* ---------- Background glow palettes ---------- */
  const PALETTES = {
    aurora: { name: 'Aurora', colors: ['#7C5CFF', '#18C8E8', '#FF6FB5'] },
    ember: { name: 'Ember', colors: ['#FF7A45', '#FFB547', '#E8456B'] },
    ocean: { name: 'Ocean', colors: ['#2F6BFF', '#18C8E8', '#5EEAD4'] },
    forest: { name: 'Forest', colors: ['#2BD47D', '#A3E635', '#14B8A6'] },
    mono: { name: 'Mono', colors: ['#9CA3AF', '#E5E7EB', '#6B7280'] }
  };
  function applyGlow(id) {
    const off = id === 'off';
    body.classList.toggle('glow-off', off);
    const palette = PALETTES[id] || PALETTES.aurora;
    if (!off) palette.colors.forEach((c, i) => root.style.setProperty('--aurora-' + (i + 1), c));
    root.dataset.glow = off ? 'off' : (PALETTES[id] ? id : 'aurora');
  }
  applyGlow(store.get('luminaria-glow') || 'aurora');

  function glowPicker() {
    const accent = document.querySelector('section[aria-labelledby="accent-heading"]');
    if (!accent || document.getElementById('glow-heading')) return;
    const section = document.createElement('section');
    section.setAttribute('aria-labelledby', 'glow-heading');
    section.className = 'glow-section';
    const heading = document.createElement('h4');
    heading.className = 'appearance-heading';
    heading.id = 'glow-heading';
    heading.textContent = 'Background glow';
    const note = document.createElement('p');
    note.className = 'note';
    note.textContent = 'The colored light behind the app. Pick one, or turn it off.';
    const row = document.createElement('div');
    row.className = 'glow-options';
    row.setAttribute('role', 'radiogroup');
    row.setAttribute('aria-labelledby', 'glow-heading');
    const current = root.dataset.glow;
    const options = [...Object.entries(PALETTES), ['off', { name: 'Off', colors: [] }]];
    for (const [id, palette] of options) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'glow-option';
      button.setAttribute('role', 'radio');
      button.setAttribute('aria-checked', String(id === current));
      button.dataset.glow = id;
      const swatch = document.createElement('span');
      swatch.className = 'glow-swatch';
      if (palette.colors.length) swatch.style.background = 'radial-gradient(circle at 30% 30%,' + palette.colors[1] + ',transparent 60%),radial-gradient(circle at 75% 70%,' + palette.colors[2] + ',transparent 60%),' + palette.colors[0];
      const label = document.createElement('span');
      label.textContent = palette.name;
      button.append(swatch, label);
      button.addEventListener('click', () => {
        store.set('luminaria-glow', id);
        applyGlow(id);
        for (const b of row.children) b.setAttribute('aria-checked', String(b === button));
      });
      row.append(button);
    }
    section.append(heading, note, row);
    accent.before(section);
  }

  /* ---------- Library menu ---------- */
  const toggle = document.getElementById('library-toggle');
  const menu = document.getElementById('library-menu');
  function setLibrary(open, focusFirst) {
    if (!toggle || !menu) return;
    if (open) {
      /* Render above everything: the glass sidebar is its own layer, so a menu inside it gets painted over by the chat. */
      if (menu.parentElement !== document.body) { document.body.append(menu); menu.classList.add('portal'); }
      const r = toggle.getBoundingClientRect();
      menu.style.left = Math.max(8, r.left - 4) + 'px';
      menu.style.bottom = Math.max(8, innerHeight - r.top + 8) + 'px';
      menu.style.width = Math.min(300, innerWidth - 16) + 'px';
      menu.style.maxHeight = Math.max(160, r.top - 24) + 'px';
    }
    menu.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    if (open && focusFirst) menu.querySelector('[role=menuitem]')?.focus();
  }
  if (toggle && menu) {
    toggle.addEventListener('click', () => setLibrary(menu.hidden, false));
    toggle.addEventListener('keydown', (e) => { if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); setLibrary(true, true); } });
    menu.addEventListener('click', (e) => { if (e.target.closest('[role=menuitem]')) setLibrary(false); });
    menu.addEventListener('keydown', (e) => {
      const items = [...menu.querySelectorAll('[role=menuitem]')];
      const i = items.indexOf(document.activeElement);
      if (e.key === 'Escape') { setLibrary(false); toggle.focus(); }
      if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
      if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
    });
    document.addEventListener('click', (e) => { if (!menu.hidden && !e.target.closest('#library') && !e.target.closest('#library-menu')) setLibrary(false); });
    addEventListener('resize', () => { if (!menu.hidden) setLibrary(false); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !menu.hidden) { setLibrary(false); toggle.focus(); } });
  }

  /* ---------- The Lumen orb ---------- */
  function orb(size) {
    const el = document.createElement('div');
    el.className = 'lumen lumen-' + size;
    el.setAttribute('aria-hidden', 'true');
    el.dataset.state = 'idle';
    for (const part of ['glow', 'swirl', 'swirl two', 'core', 'shine']) {
      const layer = document.createElement('i');
      layer.className = 'lumen-' + part.replace(' ', ' lumen-');
      el.append(layer);
    }
    return el;
  }
  const presence = document.createElement('div');
  presence.className = 'presence';
  const presenceOrb = orb('small');
  const presenceText = document.createElement('span');
  presenceText.className = 'presence-text';
  presenceText.setAttribute('role', 'status');
  presenceText.textContent = 'Ready';
  presence.append(presenceOrb, presenceText);
  document.querySelector('.topbar .breadcrumb')?.before(presence);

  const heroOrb = orb('hero');
  const welcomeMark = document.querySelector('#welcome .welcome-mark');
  if (welcomeMark) { welcomeMark.replaceWith(heroOrb); }

  const LABELS = { idle: 'Ready', working: 'Working', generating: 'Writing', listening: 'Listening', speaking: 'Speaking', waiting: 'Needs you', error: 'Problem' };
  function mirror(status) {
    const key = status.getAttribute('data-state') || 'idle';
    const text = status.querySelector('span')?.textContent?.trim();
    for (const el of [presenceOrb, heroOrb]) el.dataset.state = key;
    presenceText.textContent = text || LABELS[key] || 'Ready';
    presence.dataset.state = key;
  }
  function watchStatus() {
    const status = document.querySelector('.entity-status');
    if (!status || status.dataset.watched) return;
    status.dataset.watched = '1';
    new MutationObserver(() => mirror(status)).observe(status, { attributes: true, attributeFilter: ['data-state'], childList: true, subtree: true, characterData: true });
    mirror(status);
  }

  /* ---------- Permission chip ---------- */
  const chip = document.createElement('button');
  chip.type = 'button';
  chip.className = 'permission-chip';
  chip.hidden = true;
  chip.title = 'Change in Settings › Tools & permissions';
  chip.addEventListener('click', () => document.querySelector('[data-panel="settings"]')?.click());
  document.querySelector('.top-actions')?.prepend(chip);
  let chipLoaded = false;
  async function loadPermission() {
    if (chipLoaded || typeof window.api !== 'function' && typeof api !== 'function') return;
    chipLoaded = true;
    try {
      const settings = await api('/settings');
      const full = (settings.access_status && settings.access_status.active) === 'full' || settings.access_mode === 'full';
      chip.dataset.mode = full ? 'full' : 'review';
      chip.textContent = full ? 'Hands-free' : 'Ask me first';
      chip.setAttribute('aria-label', 'Permission mode: ' + chip.textContent + '. Open settings to change.');
      chip.hidden = false;
      if (settings.workspace_problem && typeof toast === 'function') setTimeout(() => toast(settings.workspace_problem, true), 1200);
    } catch { chipLoaded = false; }
  }
  window.addEventListener('studio-state', loadPermission);

  /* ---------- Choice cards in place of dropdowns ---------- */
  const CHOICES = {
    'access-mode': [
      ['review', 'Ask me first', 'Reads and searches run on their own. Changes, commands and network use wait for your OK.'],
      ['full', 'Hands-free', 'Everything runs without asking, using your Windows permissions. Not a sandbox. Applies after restart.']
    ]
  };
  function cards(select, options) {
    if (select.dataset.cards) return;
    select.dataset.cards = '1';
    const group = document.createElement('div');
    group.className = 'choice-cards';
    group.setAttribute('role', 'radiogroup');
    const label = select.labels && select.labels[0];
    group.setAttribute('aria-label', label ? label.textContent.trim() : 'Choose one');
    const sync = () => { for (const card of group.children) card.setAttribute('aria-checked', String(card.dataset.value === select.value)); };
    for (const [value, title, help] of options) {
      if (![...select.options].some((o) => o.value === value)) continue;
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'choice-card';
      card.setAttribute('role', 'radio');
      card.dataset.value = value;
      card.disabled = select.disabled;
      const strong = document.createElement('strong');
      strong.textContent = title;
      const small = document.createElement('small');
      small.textContent = help;
      card.append(strong, small);
      card.addEventListener('click', () => {
        select.value = value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        sync();
      });
      group.append(card);
    }
    select.addEventListener('change', sync);
    select.hidden = true;
    select.after(group);
    sync();
  }

  function enhance() {
    for (const [id, options] of Object.entries(CHOICES)) {
      const select = document.getElementById(id);
      if (select && select.tagName === 'SELECT') cards(select, options);
    }
    glowPicker();
    watchStatus();
  }
  new MutationObserver(enhance).observe(body, { childList: true, subtree: true });
  enhance();
})();

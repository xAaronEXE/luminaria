/* Luminaria dropdowns. Windows draws a <select>'s open list itself (white, ignoring the app's theme), so every
   select is given a themed button and list. The native select stays in place, hidden, as the source of truth:
   forms, FormData, `value`, and existing change handlers keep working unchanged. */
(() => {
  const done = new WeakSet();
  let openState = null;

  function textOf(sel) { const o = sel.options[sel.selectedIndex]; return o ? o.textContent : ''; }
  function labelOf(sel) {
    if (sel.getAttribute('aria-label')) return sel.getAttribute('aria-label');
    if (sel.id) { const l = document.querySelector(`label[for="${CSS.escape(sel.id)}"]`); if (l) return l.textContent.trim(); }
    const parentLabel = sel.closest('label'); return parentLabel ? parentLabel.textContent.replace(textOf(sel), '').trim() : '';
  }

  function enhance(sel) {
    if (done.has(sel) || sel.multiple || sel.size > 1 || sel.closest('[data-native-select]')) return;
    done.add(sel);
    // Not laid out yet (built off-screen)? Plain form selects fill their row; classed ones are inline controls.
    const full = sel.offsetWidth ? (sel.parentElement && sel.offsetWidth >= sel.parentElement.clientWidth * 0.9) : !sel.className;
    const wrap = document.createElement('span');
    wrap.className = 'lum-select' + (full ? ' full' : '') + (sel.className ? ' ' + sel.className : '');
    if (!full && sel.offsetWidth) wrap.style.minWidth = sel.offsetWidth + 'px';
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'lum-select-button';
    button.setAttribute('aria-haspopup', 'listbox'); button.setAttribute('aria-expanded', 'false');
    const label = labelOf(sel); if (label) button.setAttribute('aria-label', label);
    button.innerHTML = '<span class="lum-select-value"></span>';
    sel.parentNode.insertBefore(wrap, sel); wrap.append(sel, button);
    sel.classList.add('lum-select-native'); sel.tabIndex = -1; sel.setAttribute('aria-hidden', 'true');
    if (sel.id) { button.id = sel.id + '-button'; const l = document.querySelector(`label[for="${CSS.escape(sel.id)}"]`); if (l) l.htmlFor = button.id; }

    const sync = () => {
      button.querySelector('.lum-select-value').textContent = textOf(sel); button.disabled = sel.disabled;
      // Follow the original's visibility: pages hide some selects on purpose.
      wrap.hidden = sel.hidden || getComputedStyle(sel).display === 'none';
    };
    // Code sometimes sets .value without firing an event; keep the button in step.
    for (const prop of ['value', 'selectedIndex']) {
      const desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, prop);
      Object.defineProperty(sel, prop, { configurable: true, get() { return desc.get.call(this); }, set(v) { desc.set.call(this, v); sync(); } });
    }
    sel.addEventListener('change', sync);
    new MutationObserver(sync).observe(sel, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'selected', 'hidden', 'style', 'class'] });
    sync();

    button.addEventListener('click', () => (openState?.sel === sel ? close() : open(sel, button)));
    button.addEventListener('keydown', (e) => {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); if (openState?.sel !== sel) open(sel, button); }
    });
  }

  function open(sel, button) {
    close();
    const list = document.createElement('div');
    list.className = 'lum-select-list'; list.setAttribute('role', 'listbox'); list.tabIndex = -1;
    if (button.getAttribute('aria-label')) list.setAttribute('aria-label', button.getAttribute('aria-label'));
    const items = [...sel.options].map((o, i) => {
      const item = document.createElement('div');
      item.className = 'lum-select-option'; item.setAttribute('role', 'option'); item.id = 'lum-opt-' + i + '-' + Math.random().toString(36).slice(2, 7);
      item.textContent = o.textContent; item.setAttribute('aria-selected', String(i === sel.selectedIndex));
      if (o.disabled) item.setAttribute('aria-disabled', 'true');
      item.addEventListener('pointerdown', (e) => e.preventDefault());
      item.addEventListener('click', () => { if (!o.disabled) choose(i); });
      item.addEventListener('pointermove', () => setActive(i));
      list.append(item); return item;
    });
    document.body.append(list);
    let active = Math.max(0, sel.selectedIndex);
    const setActive = (i) => {
      active = i; items.forEach((el, n) => el.classList.toggle('active', n === i));
      list.setAttribute('aria-activedescendant', items[i]?.id || ''); items[i]?.scrollIntoView({ block: 'nearest' });
    };
    const choose = (i) => {
      const changed = sel.selectedIndex !== i;
      sel.selectedIndex = i; close(); button.focus();
      if (changed) { sel.dispatchEvent(new Event('input', { bubbles: true })); sel.dispatchEvent(new Event('change', { bubbles: true })); }
    };
    const place = () => {
      const r = button.getBoundingClientRect(), gap = 6, below = innerHeight - r.bottom - gap, above = r.top - gap;
      list.style.minWidth = r.width + 'px'; list.style.left = Math.min(r.left, innerWidth - list.offsetWidth - 8) + 'px';
      const up = below < Math.min(list.scrollHeight, 240) && above > below;
      list.style.maxHeight = Math.max(120, Math.min(320, (up ? above : below) - 8)) + 'px';
      list.style.top = (up ? r.top - gap - list.offsetHeight : r.bottom + gap) + 'px';
      list.classList.toggle('up', up);
    };
    let typed = '', typedAt = 0;
    const onKey = (e) => {
      if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' ', 'Escape'].includes(e.key)) e.stopPropagation();  // the list owns these keys while open
      const step = (d) => { let i = active; do { i = (i + d + items.length) % items.length; } while (sel.options[i].disabled && i !== active); setActive(i); };
      if (e.key === 'ArrowDown') { e.preventDefault(); step(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); step(-1); }
      else if (e.key === 'Home') { e.preventDefault(); setActive(0); }
      else if (e.key === 'End') { e.preventDefault(); setActive(items.length - 1); }
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (!sel.options[active]?.disabled) choose(active); }
      else if (e.key === 'Escape') { e.preventDefault(); close(); button.focus(); }
      else if (e.key === 'Tab') close();
      else if (e.key.length === 1) {
        typed = (Date.now() - typedAt > 700 ? '' : typed) + e.key.toLowerCase(); typedAt = Date.now();
        const hit = [...sel.options].findIndex((o) => o.textContent.trim().toLowerCase().startsWith(typed));
        if (hit >= 0) setActive(hit);
      }
    };
    const outside = (e) => { if (!list.contains(e.target) && e.target !== button && !button.contains(e.target)) close(); };
    const reflow = (e) => { if (e.type === 'resize' || !list.contains(e.target)) close(); };
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('pointerdown', outside, true);
    addEventListener('resize', reflow); document.addEventListener('scroll', reflow, true);
    openState = { sel, list, button, cleanup() {
      document.removeEventListener('keydown', onKey, true); document.removeEventListener('pointerdown', outside, true);
      removeEventListener('resize', reflow); document.removeEventListener('scroll', reflow, true);
    } };
    button.setAttribute('aria-expanded', 'true'); button.classList.add('open');
    setActive(active); place(); requestAnimationFrame(() => list.classList.add('shown'));
  }

  function close() {
    if (!openState) return;
    const { list, button, cleanup } = openState; openState = null;
    cleanup(); button.setAttribute('aria-expanded', 'false'); button.classList.remove('open'); list.remove();
  }

  const scan = (root) => {
    if (root.nodeType !== 1) return;
    if (root.tagName === 'SELECT') enhance(root); else root.querySelectorAll?.('select').forEach(enhance);
  };
  const start = () => {
    scan(document.body);
    new MutationObserver((records) => {
      for (const r of records) for (const node of r.addedNodes) scan(node);
      if (openState && !openState.sel.isConnected) close();
    }).observe(document.body, { childList: true, subtree: true });
  };
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', start) : start();
})();

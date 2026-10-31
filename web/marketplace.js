/* Marketplace: browse and install free skills and connectors. Same look as the model library. */
(() => {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let tab = 'skills', timer, cursor = '', seq = 0;
  const extraRepos = () => { try { return JSON.parse(localStorage.getItem('market-repos') || '[]'); } catch { return []; } };
  const saveRepos = (list) => { try { localStorage.setItem('market-repos', JSON.stringify(list)); } catch {} };

  window.renderMarketplace = async function (body) {
    body.innerHTML = `<h3 class="settings-page-title">Marketplace</h3>
      <p class="settings-intro">Free skills and connectors from public catalogs. Nothing runs until you install it, and installed items still follow your permission settings.</p>
      <div class="market-bar"><div class="segmented" role="tablist"><button type="button" role="tab" data-tab="skills">Skills</button><button type="button" role="tab" data-tab="mcp">Connectors</button></div>
      <input id="market-q" type="search" placeholder="Search…" aria-label="Search the marketplace"></div>
      <div id="market-list" class="s-card" aria-live="polite"></div>
      <div class="s-actions"><button type="button" class="text-button" id="market-more" hidden>Show more</button><button type="button" class="text-button" id="market-repo" hidden>Add a skill repository</button></div>`;
    const list = body.querySelector('#market-list'), q = body.querySelector('#market-q'), more = body.querySelector('#market-more'), addRepo = body.querySelector('#market-repo');
    const mark = () => body.querySelectorAll('[data-tab]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
    const row = (name, sub, action) => `<div class="setting-row market-row"><div><h3>${esc(name)}</h3><p>${esc(sub)}</p></div><div class="row-actions">${action}</div></div>`;
    async function load(append = false) {
      const mine = ++seq;
      if (!append) { cursor = ''; list.innerHTML = '<p class="note" role="status">Loading…</p>'; }
      try {
        let html = '';
        if (tab === 'skills') {
          const data = await api('/marketplace/skills?q=' + encodeURIComponent(q.value) + '&repos=' + encodeURIComponent(extraRepos().join(',')));
          if (mine !== seq) return;
          html = data.items.map((s) => row(s.name, s.repo + (s.folder ? ' · ' + s.folder : ''), s.installed ? '<span class="badge good">Installed</span>' : `<button class="btn" data-skill="${esc(s.repo)}" data-path="${esc(s.path)}">Install</button>`)).join('');
          if (data.errors.length) html += `<p class="note warn-note">Could not read: ${esc(data.errors.join(', '))}. Check your connection.</p>`;
          more.hidden = true;
        } else {
          const data = await api('/marketplace/mcp?q=' + encodeURIComponent(q.value) + (append && cursor ? '&cursor=' + encodeURIComponent(cursor) : ''));
          if (mine !== seq) return;
          cursor = data.next || '';
          html = data.items.map((s) => {
            const needs = s.packages[0]?.needs?.length ? 'Needs ' + s.packages[0].needs.join(', ') : '';
            const action = s.installed ? '<span class="badge good">Installed</span>' : !s.installable ? '<span class="badge">Hosted only</span>' : needs ? '<span class="badge warn">Needs a key</span>' : `<button class="btn" data-mcp="${esc(s.id)}">Install</button>`;
            return row(s.title, s.description || s.id, action);
          }).join('');
          more.hidden = !cursor;
        }
        html = html || '<p class="note">Nothing found.</p>';
        if (append) list.insertAdjacentHTML('beforeend', html); else list.innerHTML = html;
      } catch (error) { if (mine === seq) list.innerHTML = `<p class="note warn-note" role="alert">${esc(error.message)}</p>`; }
    }
    body.querySelectorAll('[data-tab]').forEach((b) => b.onclick = () => { tab = b.dataset.tab; q.value = ''; mark(); addRepo.hidden = tab !== 'skills'; load(); });
    q.oninput = () => { clearTimeout(timer); timer = setTimeout(load, 350); };
    more.onclick = () => load(true);
    addRepo.onclick = () => { const repo = prompt('GitHub repository with skills (owner/name)'); if (!repo) return; saveRepos([...new Set([...extraRepos(), repo.trim()])]); load(); };
    list.onclick = async (event) => {
      const button = event.target.closest('button[data-skill],button[data-mcp]'); if (!button) return;
      button.disabled = true; button.textContent = 'Installing…';
      try {
        if (button.dataset.skill) await api('/marketplace/skills/install', 'POST', { repo: button.dataset.skill, path: button.dataset.path });
        else await api('/marketplace/mcp/install', 'POST', { id: button.dataset.mcp });
        button.replaceWith(Object.assign(document.createElement('span'), { className: 'badge good', textContent: 'Installed' }));
        if (typeof toast === 'function') toast('Installed');
        if (typeof refresh === 'function') refresh();
      } catch (error) { button.disabled = false; button.textContent = 'Install'; if (typeof toast === 'function') toast(error.message, true); }
    };
    mark(); addRepo.hidden = tab !== 'skills'; load();
  };
})();

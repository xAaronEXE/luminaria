/* Marketplace: browse and install free skills and connectors. Same look as the model library. */
(() => {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let tab = 'skills', timer, seq = 0;
  const extraRepos = () => { try { return JSON.parse(localStorage.getItem('market-repos') || '[]'); } catch { return []; } };
  const saveRepos = (list) => { try { localStorage.setItem('market-repos', JSON.stringify(list)); } catch {} };

  window.renderMarketplace = async function (body) {
    body.innerHTML = `<h3 class="settings-page-title">Marketplace</h3>
      <p class="settings-intro" id="market-intro">Free skills and connectors. Nothing runs until you install it, and installed items still follow your permission settings.</p>
      <div class="market-bar"><div class="segmented" role="tablist"><button type="button" role="tab" data-tab="skills">Skills</button><button type="button" role="tab" data-tab="mcp">Connectors</button></div>
      <input id="market-q" type="search" placeholder="Search…" aria-label="Search the marketplace"></div>
      <div id="market-list" class="s-card" aria-live="polite"></div>
      <div class="s-actions"><button type="button" class="text-button" id="market-more" hidden>Show more</button><button type="button" class="text-button" id="market-repo" hidden>Add a skill repository</button></div>`;
    const intro = body.querySelector('#market-intro'), list = body.querySelector('#market-list'), q = body.querySelector('#market-q'), more = body.querySelector('#market-more'), addRepo = body.querySelector('#market-repo');
    const mark = () => body.querySelectorAll('[data-tab]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
    const row = (name, sub, action) => `<div class="setting-row market-row"><div><h3>${esc(name)}</h3><p>${esc(sub)}</p></div><div class="row-actions">${action}</div></div>`;
    let offset = 0;
    async function load(append = false) {
      const mine = ++seq;
      if (!append) { offset = 0; list.innerHTML = '<p class="note" role="status">Loading…</p>'; }
      try {
        const kind = tab === 'skills' ? 'skills' : 'connectors';
        const data = await api('/catalog?kind=' + kind + '&offset=' + offset + '&q=' + encodeURIComponent(q.value));
        if (mine !== seq) return;
        const counts = data.counts || {};
        intro.textContent = `${(counts.skills || 0).toLocaleString()} skills and ${(counts.connectors || 0).toLocaleString()} connectors are built in. The assistant can also find and add them for you when a task needs one. Nothing runs until it is installed, and installed items follow your permission settings.`;
        let html = data.items.map((s) => {
          const sub = s.kind === 'skill'
            ? `${s.description} · ${s.repo} · ${s.license}${s.stars ? ' · ★ ' + Number(s.stars).toLocaleString() : ''}`
            : s.description || s.id;
          const action = s.installed ? '<span class="badge good">Installed</span>'
            : !s.installable ? (s.needs?.length ? '<span class="badge warn">Needs a key</span>' : '<span class="badge">Hosted only</span>')
            : `<button class="btn" data-id="${esc(s.id)}" data-kind="${esc(s.kind)}">Install</button>`;
          return row(s.name, sub, action);
        }).join('');
        offset += data.items.length;
        more.hidden = offset >= data.total;
        if (!append && tab === 'skills' && extraRepos().length) {
          const own = await api('/marketplace/skills?q=' + encodeURIComponent(q.value) + '&repos=' + encodeURIComponent(extraRepos().join(',')));
          if (mine !== seq) return;
          html += own.items.filter((s) => extraRepos().includes(s.repo)).map((s) => row(s.name, s.repo + (s.folder ? ' · ' + s.folder : ''), s.installed ? '<span class="badge good">Installed</span>' : `<button class="btn" data-skill="${esc(s.repo)}" data-path="${esc(s.path)}">Install</button>`)).join('');
        }
        html = html || (data.total === 0 && !q.value ? '<p class="note">The built-in catalog is missing. Reinstall Luminaria to restore it.</p>' : '<p class="note">Nothing found.</p>');
        if (append) list.insertAdjacentHTML('beforeend', html); else list.innerHTML = html;
      } catch (error) { if (mine === seq) list.innerHTML = `<p class="note warn-note" role="alert">${esc(error.message)}</p>`; }
    }
    body.querySelectorAll('[data-tab]').forEach((b) => b.onclick = () => { tab = b.dataset.tab; q.value = ''; mark(); addRepo.hidden = tab !== 'skills'; load(); });
    q.oninput = () => { clearTimeout(timer); timer = setTimeout(load, 350); };
    more.onclick = () => load(true);
    addRepo.onclick = () => { const repo = prompt('GitHub repository with skills (owner/name)'); if (!repo) return; saveRepos([...new Set([...extraRepos(), repo.trim()])]); load(); };
    list.onclick = async (event) => {
      const button = event.target.closest('button[data-skill],button[data-id]'); if (!button) return;
      const label = button.closest('.market-row')?.querySelector('h3')?.textContent || 'this';
      const what = button.dataset.kind === 'connector'
        ? 'This downloads and RUNS code from a third party on your PC (' + button.dataset.id + '). Only install connectors you trust.\n\nInstall it?'
        : 'Skills are instructions the assistant will follow. A skill from a stranger can steer it, so read what you install.\n\nInstall ' + label + '?';
      if (!confirm(what)) return;
      button.disabled = true; button.textContent = 'Installing…';
      try {
        if (button.dataset.skill) await api('/marketplace/skills/install', 'POST', { repo: button.dataset.skill, path: button.dataset.path });
        else await api('/catalog/install', 'POST', { id: button.dataset.id, confirm: true });
        button.replaceWith(Object.assign(document.createElement('span'), { className: 'badge good', textContent: 'Installed' }));
        if (typeof toast === 'function') toast('Installed');
        if (typeof refresh === 'function') refresh();
      } catch (error) { button.disabled = false; button.textContent = 'Install'; if (typeof toast === 'function') toast(error.message, true); }
    };
    mark(); addRepo.hidden = tab !== 'skills'; load();
  };
})();

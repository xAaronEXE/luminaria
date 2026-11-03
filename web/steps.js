/* Tool steps in the chat: plain-English, grouped and collapsed, like "Ran 2 commands, read 3 files ▸".
   Raw arguments and output stay one click deeper for anyone who wants them. */
(() => {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const base = (p) => String(p || '').split(/[\\/]/).filter(Boolean).pop() || String(p || '');
  const where = (p) => (!p || p === '.' || p === './') ? 'the default folder' : base(p);
  const quote = (q) => { q = String(q || '').trim(); return q ? `“${q.length > 60 ? q.slice(0, 57) + '…' : q}”` : ''; };
  const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return 'a web page'; } };
  const human = (name) => String(name).replace(/[_-]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

  // [label, kind] — kind drives the group summary.
  function describe(name, a = {}) {
    switch (name) {
      case 'list_files': return [`Listed files in ${where(a.path)}`, 'list'];
      case 'read_file': return [`Read ${base(a.path)}`, 'read'];
      case 'write_file': return [`Wrote ${base(a.path)}`, 'write'];
      case 'edit_file': return [`Edited ${base(a.path)}`, 'write'];
      case 'delete_file': return [`Deleted ${base(a.path)}`, 'delete'];
      case 'search_files': return [`Searched files for ${quote(a.query)}`, 'search'];
      case 'run_command': return ['Ran a command', 'command'];
      case 'run_code': return [`Ran ${a.language === 'javascript' ? 'JavaScript' : 'Python'} code`, 'command'];
      case 'research': return [`Researched ${quote(a.question)}`, 'websearch'];
      case 'web_search': return [`Searched the web for ${quote(a.query)}`, 'websearch'];
      case 'web_fetch': return [`Read ${host(a.url)}`, 'webread'];
      case 'memory_search': return [`Searched memory for ${quote(a.query)}`, 'memory'];
      case 'remember': return [`Saved “${a.title || 'a note'}” to memory`, 'memory'];
      case 'history_read': return ['Looked back in the conversation', 'memory'];
      case 'list_skills': return ['Checked available skills', 'skill'];
      case 'load_skill': return [`Used the ${a.name || ''} skill`, 'skill'];
      case 'finish_skill': return [`Checked the ${a.name || ''} skill's results`, 'skill'];
      case 'find_capability': return [`Looked for skills and connectors: ${quote(a.query)}`, 'skill'];
      case 'install_capability': return [`Added ${base(String(a.id || '').split(':').pop().replace(/\/SKILL\.md$/, '')) || 'a capability'}`, 'skill'];
      case 'discover_tools': return [`Loaded ${a.category === 'all' ? 'connector' : a.category} tools`, 'other'];
      case 'update_plan': return ['Updated the plan', 'plan'];
      case 'update_brief': return ['Updated the working brief', 'plan'];
      case 'create_schedule': return [`Scheduled “${a.title || 'a task'}”`, 'other'];
      case 'create_file_workflow': return ['Proposed a file workflow', 'other'];
    }
    if (name.includes('__')) { const [group, tool] = name.split('__'); return [`${human(group)}: ${human(tool).toLowerCase()}`, group === 'browser' ? 'browser' : 'app']; }
    return [human(name), 'other'];
  }
  const n_ = (n, one, many) => n === 1 ? one : many.replace('#', n);
  const PHRASES = {
    list: (n) => n_(n, 'listed files', 'listed # folders'),
    read: (n) => n_(n, 'read a file', 'read # files'),
    write: (n) => n_(n, 'changed a file', 'changed # files'),
    delete: (n) => n_(n, 'deleted a file', 'deleted # files'),
    search: (n) => n_(n, 'searched your files', 'searched your files # times'),
    command: (n) => n_(n, 'ran a command', 'ran # commands'),
    websearch: (n) => n_(n, 'searched the web', 'searched the web # times'),
    webread: (n) => n_(n, 'read a web page', 'read # web pages'),
    browser: (n) => n_(n, 'used the browser', 'took # browser steps'),
    memory: () => 'checked memory', skill: (n) => n_(n, 'used a skill', 'used # skills'), plan: () => 'updated the plan',
    app: (n) => n_(n, 'used a connected app', 'took # actions in connected apps'), other: (n) => n_(n, 'used a tool', 'used # tools'),
  };
  function summary(rows) {
    if (rows.length === 1) return rows[0].label;
    const kinds = new Map(); for (const r of rows) kinds.set(r.kind, (kinds.get(r.kind) || 0) + 1);
    const parts = [...kinds].map(([k, n]) => PHRASES[k](n));
    const shown = parts.slice(0, 3), rest = rows.length - [...kinds].slice(0, 3).reduce((t, [, n]) => t + n, 0);
    const text = rest > 0 ? shown.join(', ') + ` and ${rest} more step${rest === 1 ? '' : 's'}` : shown.length > 1 ? shown.slice(0, -1).join(', ') + ' and ' + shown.at(-1) : shown[0];
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  const ATTENTION = { waiting: 'Waiting for your approval', requested: 'Waiting for your approval', running: 'Working…', failed: 'Failed', error: 'Failed', denied: 'Not allowed', interrupted: 'Stopped', cancelled: 'Cancelled' };

  // A collapsible group. add() appends one tool call; refresh() updates the summary line.
  window.stepGroup = function () {
    const el = document.createElement('details'); el.className = 'steps';
    el.innerHTML = '<summary><span class="steps-title"></span><span class="steps-note"></span></summary><div class="steps-list"></div>';
    const rows = [];
    const api = {
      el,
      add(call, action) {
        let args = action?.args; if (!args) { try { args = JSON.parse(call.function.arguments || '{}'); } catch { args = {}; } }
        const [label, kind] = describe(call.function.name, args || {});
        const status = action?.status || 'requested';
        rows.push({ label, kind, status });
        const row = document.createElement('details'); row.className = 'step ' + status;
        const note = ATTENTION[status] ? `<span class="step-note ${esc(status)}">${esc(ATTENTION[status])}</span>` : '';
        const output = action?.result ? (action.result.text || JSON.stringify(action.result, null, 2)) : '';
        row.innerHTML = `<summary><span>${esc(label)}</span>${note}</summary><div class="step-detail"><div class="step-tool">${esc(call.function.name.replace('__', ' · '))}</div><pre>${esc(JSON.stringify(args, null, 2))}</pre>${output ? `<pre>${esc(output.length > 4000 ? output.slice(0, 4000) + '\n…' : output)}</pre>` : ''}</div>`;
        el.querySelector('.steps-list').append(row);
        api.refresh();
      },
      refresh() {
        el.querySelector('.steps-title').textContent = summary(rows);
        // A single step needs no inner list: opening the group shows its details directly.
        const single = rows.length === 1; el.classList.toggle('single', single);
        el.querySelectorAll('.step').forEach((row) => { if (single) row.open = true; });
        const waiting = rows.filter((r) => r.status === 'waiting' || r.status === 'requested').length;
        const failed = rows.filter((r) => r.status === 'failed' || r.status === 'error').length, running = rows.some((r) => r.status === 'running');
        const note = waiting ? 'Waiting for your approval' : running ? 'Working…' : failed ? `${failed} failed` : '';
        const n = el.querySelector('.steps-note'); n.textContent = note; n.className = 'steps-note' + (waiting ? ' waiting' : failed ? ' failed' : running ? ' running' : '');
        if (waiting) el.open = true; // an approval should never be hidden
      },
    };
    return api;
  };
  window.describeStep = describe;
})();

/* Extensions: one place for skills, connectors and workflows.
   Every item uses the same card: icon, name, one line about it, a status, one main action, and a details area
   that holds its setup as numbered steps. Opening Skills, Integrations, Automations or the Marketplace lands here. */
(() => {
  const TABS = [['installed', 'Installed'], ['browse', 'Browse'], ['skills', 'Skills'], ['connectors', 'Connectors'], ['workflows', 'Workflows']];
  const KIND = { skill: ['book', 'Skill'], connector: ['plug', 'Connector'], workflow: ['clock', 'Workflow'] };
  const SETUP_LINKS = { github: 'https://github.com/settings/personal-access-tokens/new', slack: 'https://api.slack.com/apps', gmail: 'https://console.cloud.google.com/auth/clients', google_drive: 'https://console.cloud.google.com/auth/clients', google_calendar: 'https://console.cloud.google.com/auth/clients' };
  const title = (name) => String(name).replaceAll('-', ' ').replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  let tab = 'installed', query = '', browseKind = 'skill', openKey = '', data = null, poll = 0, browseSeq = 0, browseOffset = 0;

  const extraRepos = () => { try { return JSON.parse(localStorage.getItem('market-repos') || '[]'); } catch { return []; } };
  const saveRepos = (list) => { try { localStorage.setItem('market-repos', JSON.stringify(list)); } catch {} };

  // ---- one card for everything ----
  function card(item) {
    const [glyph, label] = KIND[item.kind];
    const open = openKey === item.key;
    return `<article class="ext-card${open ? ' open' : ''}" data-key="${esc(item.key)}">
      <div class="ext-head">
        <button type="button" class="ext-main" aria-expanded="${open}" aria-controls="body-${esc(item.key)}">
          <span class="ext-icon ext-${item.kind}">${icon(item.glyph || glyph)}</span>
          <span class="ext-text"><strong>${esc(item.name)}</strong><small>${esc(item.about || '')}</small>
          <span class="ext-meta">${esc([item.label ?? label, ...(item.meta || [])].filter(Boolean).join(' · '))}</span></span>
        </button>
        <span class="ext-side">${item.status ? `<span class="ext-status ${item.tone || ''}" role="status">${esc(item.status)}</span>` : ''}
        ${item.action && !(open && item.action.id === 'open') ? `<button type="button" class="btn ${item.action.primary ? 'primary' : ''}" data-act="${esc(item.action.id)}">${esc(item.action.label)}</button>` : ''}
        <button type="button" class="ext-chevron" aria-label="${open ? 'Hide' : 'Show'} details for ${esc(item.name)}" data-toggle>${icon('chevron')}</button></span>
      </div>
      <div class="ext-body" id="body-${esc(item.key)}" ${open ? '' : 'hidden'}>${open ? item.body() : ''}</div>
    </article>`;
  }
  const steps = (list) => `<ol class="ext-steps">${list.map(([head, text, extra], i) => `<li><span class="ext-step-n">${i + 1}</span><div><strong>${esc(head)}</strong>${text ? `<p>${text}</p>` : ''}${extra || ''}</div></li>`).join('')}</ol>`;
  const actions = (html) => `<div class="ext-actions">${html}</div>`;

  // ---- items ----
  function skillItems() {
    return data.skills.map((s) => {
      const off = s.enabled === false, ready = s.available && !off;
      return { kind: 'skill', key: 'skill:' + s.name, name: title(s.name), about: s.description, meta: [s.local ? 'Added by you' : 'Built in', s.category],
        status: off ? 'Off' : s.available ? 'Ready' : 'Needs setup', tone: off ? '' : s.available ? 'good' : 'warn',
        action: ready ? { id: 'use-skill', label: 'Use' } : !s.available && !off ? { id: 'open', label: 'Set up', primary: true } : null,
        search: [s.name, s.description, s.category].join(' '), installed: true, raw: s,
        body: () => (s.missing.length ? `<h4>Set up</h4>` + steps(s.missing.map((m) => [m, ...missingHelp(m)])) : '')
          + (s.requires.length ? `<p class="small-note">Uses: ${s.requires.map(esc).join(', ')}</p>` : '')
          + `<details class="ext-more" data-instructions="${esc(s.name)}"><summary>Read the instructions</summary><div class="markdown"></div></details>`
          + actions(`<label class="switch"><input type="checkbox" data-skill-toggle="${esc(s.name)}" ${off ? '' : 'checked'}> On</label>
            <button type="button" class="btn" data-use="${esc(s.name)}" ${off ? 'disabled' : ''}>Use in this task</button>
            ${s.local ? `<button type="button" class="btn danger" data-remove-skill="${esc(s.name)}">Remove</button>` : ''}`) };
    });
  }
  function missingHelp(m) {
    const go = (where, label) => `<button type="button" class="btn" data-goto="${where}">${label} ${icon('arrow-right')}</button>`;
    if (/default folder|working folder/i.test(m)) return ['Choose a default folder that Luminaria can open.', go('settings:Default folder', 'Open Default folder')];
    if (/browser|windows|command|python|node/i.test(m)) return ['Turn on Computer and command tools. The built-in connectors start by themselves.', go('settings:Tools & permissions', 'Open Permissions')];
    const service = data.integrations.find((i) => m.toLowerCase().includes(i.label.toLowerCase()) || m.toLowerCase().includes(i.id));
    if (service) return [`Connect ${esc(service.label)}. It takes about a minute.`, go('service:' + service.id, 'Set up ' + esc(service.label))];
    return ['Connect or turn on ' + esc(m) + ', then come back here.', go('tab:connectors', 'Open Connectors')];
  }
  function integrationStatus(i) {
    return i.connected ? ['good', 'Connected'] : /waiting|sign in/i.test(i.status || '') ? ['warn', 'Waiting for sign-in']
      : i.configured && /connecting|starting/i.test(i.status || '') ? ['warn', 'Connecting'] : i.configured ? ['bad', 'Not working'] : ['', 'Not connected'];
  }
  function connectorItems() {
    const presets = new Set(data.integrations.map((i) => i.id));
    const services = data.integrations.map((i) => {
      const [tone, status] = integrationStatus(i);
      return { kind: 'connector', key: 'service:' + i.id, name: i.label, about: i.about, meta: [i.connected ? i.tools + ' tools' : 'Signs in with ' + (i.auth === 'token' ? 'a token' : 'your browser')],
        status, tone, action: i.connected ? null : { id: 'open', label: i.configured ? 'Fix' : 'Set up', primary: !i.configured },
        search: i.label + ' ' + i.about, installed: !!i.configured, body: () => serviceBody(i) };
    });
    const custom = Object.entries(state.connectors || {}).filter(([n]) => !presets.has(n)).map(([n, c]) => {
      const ok = c.status === 'connected', builtIn = ['browser', 'windows'].includes(n);
      return { kind: 'connector', key: 'mcp:' + n, glyph: n === 'browser' ? 'globe' : 'plug', name: title(n), about: builtIn ? (n === 'browser' ? 'Opens and reads web pages in Edge.' : 'Uses apps and windows on this PC.') : 'A connector you added.',
        meta: [builtIn ? 'Built in' : 'Added by you', (c.tools || 0) + ' tools'], status: ok ? 'Connected' : 'Unavailable', tone: ok ? 'good' : 'warn',
        search: n, installed: true,
        body: () => (ok ? '' : `<h4>Set up</h4>` + steps([['Turn on computer tools', 'Connectors run only when Computer and command tools is on in Settings › Permissions.'], ['Check its status', esc(c.status || 'Not started') + '. It reconnects when Luminaria restarts.']]))
          + actions(builtIn ? '' : `<button type="button" class="btn danger" data-remove-connector="${esc(n)}">Remove</button>`) };
    });
    return [...services, ...custom];
  }
  function serviceBody(i) {
    const token = i.auth === 'token';
    return (i.configured && !i.connected ? `<p class="ext-alert">${esc(i.status)}</p>` : '')
      + steps([
        [token || i.needs_client_id ? 'Prepare access' : 'Continue in your browser', esc(i.setup), SETUP_LINKS[i.id] ? `<a class="btn" href="${SETUP_LINKS[i.id]}" target="_blank" rel="noopener noreferrer">Open ${esc(i.label)} setup ${icon('arrow-right')}</a>` : ''],
        [token ? 'Paste your token and connect' : 'Review and authorize', token ? 'Keep read-only on unless your tasks need changes.' : 'Choose the account and permissions on the provider’s page. You can cancel there.',
          (i.needs_client_id ? `<label class="field">Redirect URL<span class="copy-row"><input readonly value="${esc(data.redirect)}" aria-label="Redirect URL"><button type="button" class="btn" data-copy="${esc(data.redirect)}">Copy</button></span></label>` : '')
          + `<form class="ext-form" data-service="${esc(i.id)}">${token ? field(i.token_label, 'token', '', 'password', true, i.saved_token ? 'A token is saved. Leave blank to keep it.' : '') : ''}${i.needs_client_id ? field('OAuth client ID', 'client_id', i.client_id, 'text', true) : ''}${i.needs_client_secret ? field('OAuth client secret', 'client_secret', '', 'password', true, i.saved_client_secret ? 'A secret is saved. Leave blank to keep it.' : '') : ''}${i.can_readonly ? `<label class="switch"><input type="checkbox" name="readonly" ${i.readonly || !i.configured ? 'checked' : ''}> Read-only access</label>` : ''}
          <div class="ext-actions"><button class="btn primary">${i.auth === 'oauth' ? (i.configured ? 'Sign in again' : 'Connect with browser') : (i.configured ? 'Save and reconnect' : 'Connect')}</button>${i.configured ? `<button type="button" class="btn danger" data-disconnect="${esc(i.id)}">Disconnect</button>` : ''}</div></form>`],
        ['Connected', 'Luminaria shows Connected only after the service answers and its tools load. Keys stay encrypted on this PC.'],
      ]);
  }
  function workflowItems() {
    const schedules = (state.schedules || []).map((s) => ({ kind: 'workflow', key: 'auto:' + s.id, name: s.title, about: s.prompt, meta: ['Every ' + Math.round(s.interval / 60) + ' minutes'],
      status: s.enabled ? 'On' : 'Paused', tone: s.enabled ? 'good' : '', search: s.title + ' ' + s.prompt, installed: true,
      action: { id: 'toggle-auto', label: s.enabled ? 'Pause' : 'Resume' },
      body: () => `<p class="small-note">${s.enabled ? 'Next run: ' + esc(new Date(s.next_run * 1000).toLocaleString()) : 'Paused. It will not run until you resume it.'} It runs while Luminaria is open and follows your permission mode.</p>`
        + actions(`<button type="button" class="btn danger" data-delete-auto="${s.id}">Delete</button>`), raw: s }));
    const files = data.fileWorkflows;
    const fileCard = { kind: 'workflow', key: 'files', glyph: 'file', name: 'File workflows', about: 'Reviewable plans for changing many files, run one checked step at a time.',
      meta: ['Built in'], status: files.length ? files.length + ' saved' : 'Ready', tone: 'good', search: 'file workflows plans', installed: files.length > 0,
      action: { id: 'open-files', label: 'Open' }, body: () => `<p class="small-note">Ask Luminaria to “plan the changes first”, or create one yourself. Each step keeps a recovery copy.</p>` + actions('<button type="button" class="btn" data-act-files>Open file workflows</button>') };
    const create = { kind: 'workflow', key: 'new-auto', glyph: 'plus', name: 'New automation', about: 'Run a prompt on a schedule, like a daily summary of a folder.', meta: [], status: '', tone: '', search: 'new automation schedule', installed: false,
      action: { id: 'open', label: 'Create', primary: true },
      body: () => steps([['Name it and choose how often', '', `<form class="ext-form" id="auto-form"><div class="form-grid">${field('Name', 'title', '', 'text', true)}${field('Every (minutes, at least 5)', 'interval_minutes', 60, 'number', true)}</div><label class="field">What should Luminaria do?<textarea name="prompt" required placeholder="Summarize new files in D:\\Reports and save a short report on my Desktop."></textarea></label><div class="ext-actions"><button class="btn primary">Create automation</button></div></form>`], ['It runs on its own', 'While Luminaria is open, following your permission mode. Pause or delete it here any time.']]) };
    return [create, ...schedules, fileCard];
  }
  // ---- model services (Relay) and other PCs ----
  const PRESETS = [['OpenRouter', 'https://openrouter.ai/api/v1'], ['Groq', 'https://api.groq.com/openai/v1'], ['Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai'],
    ['OmniRoute', 'http://localhost:20128/v1'], ['Ollama', 'http://localhost:11434/v1'], ['LM Studio', 'http://localhost:1234/v1']];
  function serviceItems() {
    const rows = data.services.filter((s) => s.kind !== 'pc').map((s) => { const on = s.enabled || s.models; return ({ kind: 'connector', label: 'Model service', key: 'svc:' + s.id, glyph: 'globe', name: s.name, about: s.url,
      meta: [`${on.length} of ${s.models.length} models in use`, s.files ? 'May see your files' : 'Conversation text only'],
      status: on.length ? 'Connected' : 'Choose models', tone: on.length ? 'good' : 'warn', action: on.length ? null : { id: 'open', label: 'Choose', primary: true },
      search: s.name + ' ' + s.url + ' ' + s.models.join(' '), installed: true,
      body: () => `<p class="small-note">Its models appear in the model picker under Model services, and you can give them roles in Settings › Model roles. Planning and final checks can stay on this PC.</p>
        <label class="switch"><input type="checkbox" data-svc-files="${esc(s.id)}" ${s.files ? 'checked' : ''}> May see my files and tool results</label>
        <p class="small-note">When this is off, the service only receives the conversation text: no file contents, no command output and no file tools.</p>
        <h4>Models to use</h4><p class="small-note">Ticked models appear in the model picker and can be given roles. Free ones often end in <code>:free</code>.</p>
        <input type="search" class="filter-input" data-svc-filter placeholder="Find a model…" aria-label="Find a model">
        <div class="svc-models" data-svc-models="${esc(s.id)}">${s.models.map((m) => `<label class="switch svc-model"><input type="checkbox" value="${esc(m)}" ${on.includes(m) ? 'checked' : ''}> ${esc(m)}</label>`).join('')}</div>`
        + actions(`<button type="button" class="btn primary" data-save-models="${esc(s.id)}">Save model choice</button><button type="button" class="btn" data-refresh-svc="${esc(s.id)}">Refresh list</button><button type="button" class="btn danger" data-remove-svc="${esc(s.id)}">Remove</button>`) }); });
    rows.push({ kind: 'connector', label: 'Model service', key: 'add-svc', glyph: 'plus', name: 'Add a model service', about: 'Use free or paid AI models online, or apps like Ollama and LM Studio, alongside your local models.', meta: ['OpenRouter, Groq, Gemini, OmniRoute, Ollama, LM Studio'],
      status: '', action: { id: 'open', label: 'Add', primary: true }, search: 'model service openrouter groq gemini omniroute ollama lm studio relay api key',
      body: () => steps([['Pick a service', 'Or enter any address that works like OpenAI\'s API.', `<div class="ext-actions">${PRESETS.map(([n, u]) => `<button type="button" class="btn" data-preset="${esc(u)}" data-preset-name="${esc(n)}">${esc(n)}</button>`).join('')}</div>`],
        ['Enter its details', 'Keys are encrypted on this PC.', `<form class="ext-form" id="svc-form">${field('Name', 'name', '', 'text', true)}${field('Address', 'url', '', 'text', true)}${field('API key (if it needs one)', 'key', '', 'password', false)}
          <label class="switch"><input type="checkbox" name="files"> May see my files and tool results</label><div class="ext-actions"><button class="btn primary">Connect</button></div></form>`],
        ['Use it', 'Its models appear in the model picker. Give them a role in Settings › Model roles, for example to do coding steps while your local model plans and checks.']]) });
    return rows;
  }
  function pcItems() {
    const sh = data.sharing; if (!sh) return [];
    const rows = [
      { kind: 'connector', label: 'This PC', key: 'pc-allow', glyph: 'models', name: 'Let other PCs pair with this one', about: `Lets your other PCs use this PC (${sh.name}) and its models.`, meta: ['Your local network'],
        status: sh.share.on ? 'On' : 'Off', tone: sh.share.on ? 'good' : '', search: 'pair share models other pc network', installed: sh.share.on,
        body: () => steps([['Turn it on', 'Windows may ask to allow Luminaria on private networks: choose Allow. Only paired PCs can use this PC, and only for running models.', `<label class="switch"><input type="checkbox" data-share ${sh.share.on ? 'checked' : ''}> Let other PCs pair</label>`],
          ['On the other PC', sh.share.on ? (sh.share.code ? `Open Settings › Paired PCs › <strong>Pair with another PC</strong>, choose <strong>${esc(sh.name)}</strong> and enter this code:<div class="pair-code">${esc(sh.share.code)}</div>The code works once, for 10 minutes.` : 'The code was used or expired.')
            : 'Turn it on to get a pairing code.', sh.share.on ? `<button type="button" class="btn" data-new-code>New code</button>${sh.share.addresses.length ? `<p class="small-note">This PC's address: ${sh.share.addresses.map(esc).join(', ')}</p>` : ''}` : '']]) },
      { kind: 'connector', label: '', key: 'pc-pair', glyph: 'plus', name: 'Pair with another PC', about: 'Use another PC running Luminaria: its models join yours, and Luminaria picks the best one for each job.', meta: [],
        status: '', action: { id: 'open', label: 'Pair', primary: true }, search: 'pair another pc computer',
        body: () => steps([['On the other PC', 'Turn on "Let other PCs pair with this one". It shows a 6-digit code.'],
          ['Find it', '', `<div class="ext-actions"><button type="button" class="btn" data-find-pcs>Look for PCs</button></div><div data-found-pcs></div>`],
          ['Enter the code', 'If it was not found, type its address instead.', `<form class="ext-form" id="pair-form"><div class="form-grid">${field('PC address', 'address', '', 'text', false)}${field('Pairing code', 'code', '', 'text', false)}</div><div class="ext-actions"><button class="btn primary">Pair</button></div></form>`]]) },
      ...sh.paired.map((pc) => ({ kind: 'connector', label: 'Paired PC', key: 'pc:' + pc.id, glyph: 'models', name: pc.name, about: 'Paired PC. Its models are used like your own: by Auto, by the roles and by plans.', meta: [pc.models + ' models', pc.url.replace(/\/v1$/, '')],
        status: 'Paired', tone: 'good', search: 'paired pc ' + pc.name, installed: true,
        body: () => `<p class="small-note">Luminaria can plan on one PC while the other codes, passing the work back and forth step by step. Your files stay on this PC; the paired PC only runs the model.</p>`
          + actions(`<button type="button" class="btn" data-refresh-svc="${esc(pc.id)}">Refresh its models</button><button type="button" class="btn danger" data-remove-svc="${esc(pc.id)}">Unpair</button>`) })),
    ];
    if (sh.paired.length) rows.push({ kind: 'connector', label: 'All paired PCs', key: 'pc-split', glyph: 'models', name: 'Split big models across paired PCs', about: 'Runs one model on this PC\'s and your paired PCs\' graphics cards together, for models too big for one PC.', meta: ['Uses llama.cpp RPC · home or office network only'],
      status: sh.split ? 'On' : 'Off', tone: sh.split ? 'good' : '', search: 'split model gpu rpc combine', installed: sh.split,
      body: () => steps([['Turn it on', 'The paired PCs lend their graphics cards automatically. llama.cpp\'s RPC has no password, so only use this on a network you trust.', `<label class="switch"><input type="checkbox" data-split ${sh.split ? 'checked' : ''}> Split big models</label>`],
        ['It reloads the model', 'The next message loads the model across all the PCs. Turning it off goes back to this PC only.']]) });
    return rows;
  }

  function addOwnItems(kind) {
    if (kind === 'skill') return [{ kind: 'skill', key: 'import-skill', glyph: 'plus', name: 'Add your own skill', about: 'Import a SKILL.md or Markdown file with instructions Luminaria should follow.', meta: [], status: '', search: 'import own skill', action: { id: 'open', label: 'Import', primary: true },
      body: () => steps([['Choose the file', 'A Markdown file up to 20,000 characters.', '<input type="file" accept=".md,text/markdown" id="skill-file" class="ext-file">'], ['Check the name and text', '', `<form class="ext-form" id="skill-form">${field('Name', 'name', '', 'text', true)}<label class="field">Instructions<textarea name="content" required></textarea></label><div class="ext-actions"><button class="btn primary">Save skill</button></div></form>`]]) }];
    return [{ kind: 'connector', key: 'add-mcp', glyph: 'plus', name: 'Add your own connector', about: 'Run any MCP server on this PC, for services without a built-in connector.', meta: ['Advanced'], status: '', search: 'custom mcp connector', action: { id: 'open', label: 'Add', primary: true },
      body: () => steps([['Only add servers you trust', 'They run with your Windows permissions.'], ['Enter how to start it', '', `<form class="ext-form" id="mcp-form">${field('Name (lowercase)', 'name', '', 'text', true)}${field('Program', 'command', '', 'text', true)}<label class="field">Arguments (JSON list)<textarea name="args" required>["serve"]</textarea></label><div class="ext-actions"><button class="btn primary">Save and start</button></div></form>`], ['It starts right away', 'Its tools appear once it answers.']]) }];
  }

  // ---- catalog (Browse) ----
  function catalogItem(s) {
    const isSkill = s.kind === 'skill';
    const status = s.installed ? 'Installed' : !s.installable ? (s.needs?.length ? 'Needs a key' : 'Hosted only') : 'Free';
    return { kind: isSkill ? 'skill' : 'connector', key: 'cat:' + s.id, name: title(s.name), about: s.description || s.id,
      meta: isSkill ? [s.repo, s.license, s.stars ? '★ ' + Number(s.stars).toLocaleString() : ''] : [s.id], status, tone: s.installed ? 'good' : !s.installable ? 'warn' : '',
      action: s.installed || !s.installable ? null : { id: 'install', label: 'Install', primary: true }, raw: s,
      body: () => s.installed ? `<p class="small-note">Installed. Find it in the ${isSkill ? 'Skills' : 'Connectors'} tab.</p>`
        : !s.installable ? `<p class="small-note">${s.needs?.length ? 'This connector needs ' + s.needs.map(esc).join(', ') + ' before it can run, so it can’t be installed in one click yet.' : 'This connector only runs on its maker’s servers, so it can’t be installed on this PC.'}</p>`
        : steps([['Review it', isSkill ? 'A skill is a set of instructions Luminaria follows. Read it before installing, since a skill can steer what Luminaria does.' : 'A connector downloads and runs code from its maker on your PC. Install only ones you trust.'],
          ['Install', 'One click. ' + (isSkill ? 'It works right away.' : 'It starts right away and follows your permission settings.'), actions(`<button type="button" class="btn primary" data-act-install>Install ${esc(title(s.name))}</button>`)]]) };
  }

  // ---- rendering ----
  const matches = (item) => !query || (item.search || item.name).toLowerCase().includes(query.toLowerCase());
  function section(heading, items, empty) {
    const shown = items.filter(matches);
    if (!shown.length && !empty) return '';
    return `<section class="ext-section"><h3 class="ext-heading">${esc(heading)} <span class="count">${shown.length}</span></h3>${shown.map(card).join('') || `<p class="note">${empty}</p>`}</section>`;
  }
  let current = [];
  function draw() {
    const root = $('#ext-root'); if (!root) return;
    const skills = skillItems(), connectors = connectorItems(), workflows = workflowItems();
    let html = '';
    if (tab === 'installed') {
      current = [...skills.filter((i) => i.installed), ...connectors.filter((i) => i.installed), ...workflows.filter((i) => i.installed)];
      html = section('Skills', skills.filter((i) => i.installed), 'No skills match.') + section('Connectors', connectors.filter((i) => i.installed), 'Nothing connected yet. Open the Connectors tab to set one up.') + section('Workflows', workflows.filter((i) => i.installed), 'No automations yet. Open the Workflows tab to create one.');
    } else if (tab === 'skills') {
      const own = addOwnItems('skill'); current = [...skills, ...own];
      const ready = skills.filter((i) => i.status === 'Ready'), setup = skills.filter((i) => i.status === 'Needs setup'), off = skills.filter((i) => i.status === 'Off');
      html = section('Needs setup', setup) + section('Ready', ready, 'No skills match.') + section('Off', off) + section('Add your own', own);
    } else if (tab === 'connectors') {
      const own = addOwnItems('connector'); current = [...connectors, ...own];
      html = section('Connected', connectors.filter((i) => i.status === 'Connected')) + section('Needs attention', connectors.filter((i) => i.installed && i.status !== 'Connected'))
        + section('Ready to set up', connectors.filter((i) => !i.installed), 'No services match.') + section('Add your own', own);
    } else if (tab === 'workflows') {
      current = workflows; html = section('Workflows', workflows, 'No workflows match.');
    }
    if (tab === 'browse') { root.innerHTML = browseShell(); bindBrowse(); return; }
    root.innerHTML = html + (tab === 'skills' || tab === 'connectors' ? `<p class="ext-foot">Looking for more? <button type="button" class="text-button" data-goto-browse="${tab === 'skills' ? 'skill' : 'connector'}">Browse ${data.counts[tab === 'skills' ? 'skills' : 'connectors'].toLocaleString()} free ${tab}</button></p>` : '');
    bind(root);
  }
  function browseShell() {
    return `<div class="ext-browse-bar"><div class="ext-tabs ext-sub" role="tablist" aria-label="What to browse">
      <button type="button" role="tab" data-browse="skill" aria-selected="${browseKind === 'skill'}">Skills <span class="count">${data.counts.skills.toLocaleString()}</span></button>
      <button type="button" role="tab" data-browse="connector" aria-selected="${browseKind === 'connector'}">Connectors <span class="count">${data.counts.connectors.toLocaleString()}</span></button></div>
      ${browseKind === 'skill' ? '<button type="button" class="text-button" id="ext-repo">Add a skill repository</button>' : ''}</div>
      <div id="ext-browse" aria-live="polite"><p class="note" role="status">Loading…</p></div><div class="ext-foot"><button type="button" class="btn" id="ext-more" hidden>Show more</button></div>`;
  }
  function bindBrowse() {
    $$('[data-browse]').forEach((b) => b.onclick = () => { browseKind = b.dataset.browse; draw(); });
    const repo = $('#ext-repo'); if (repo) repo.onclick = () => { const r = prompt('GitHub repository with skills (owner/name)'); if (!r) return; saveRepos([...new Set([...extraRepos(), r.trim()])]); loadBrowse(); };
    $('#ext-more').onclick = () => loadBrowse(true);
    loadBrowse();
  }
  async function loadBrowse(append = false) {
    const mine = ++browseSeq, list = $('#ext-browse'); if (!list) return;
    if (!append) { browseOffset = 0; current = []; }
    try {
      const res = await api(`/catalog?kind=${browseKind === 'skill' ? 'skills' : 'connectors'}&offset=${browseOffset}&q=${encodeURIComponent(query)}`);
      if (mine !== browseSeq || !$('#ext-browse')) return;
      let items = res.items.map(catalogItem);
      if (!append && browseKind === 'skill' && extraRepos().length) {
        const own = await api('/marketplace/skills?q=' + encodeURIComponent(query) + '&repos=' + encodeURIComponent(extraRepos().join(',')));
        items = items.concat(own.items.filter((s) => extraRepos().includes(s.repo)).map((s) => ({ ...catalogItem({ kind: 'skill', id: s.repo + ':' + s.path, name: s.name, description: s.repo + (s.folder ? ' · ' + s.folder : ''), repo: s.repo, installed: s.installed, installable: true }), repoSkill: s })));
      }
      browseOffset += res.items.length; current = current.concat(items);
      $('#ext-more').hidden = browseOffset >= res.total;
      const html = items.map(card).join('');
      if (append) list.insertAdjacentHTML('beforeend', html);
      else list.innerHTML = html || (res.total === 0 && !query ? '<p class="note">The built-in catalog is missing. Reinstall Luminaria to restore it.</p>' : '<p class="note">Nothing found. Try other words.</p>');
      bind(list);
    } catch (error) { if (mine === browseSeq) list.innerHTML = `<p class="ext-alert" role="alert">${esc(error.message)}</p>`; }
  }

  // ---- behaviour ----
  function rerenderCard(key) {
    const el = document.querySelector(`.ext-card[data-key="${CSS.escape(key)}"]`), item = current.find((i) => i.key === key);
    if (!el || !item) return;
    el.outerHTML = card(item); const fresh = document.querySelector(`.ext-card[data-key="${CSS.escape(key)}"]`); bind(fresh);
  }
  function toggle(key, force) {
    const was = openKey; openKey = force ?? (openKey === key ? '' : key);
    if (was && was !== openKey) rerenderCard(was);
    rerenderCard(key);
    if (openKey === key) document.querySelector(`.ext-card[data-key="${CSS.escape(key)}"] .ext-body`)?.querySelector('input,textarea,button,a')?.focus({ preventScroll: true });
  }
  async function reload(keepTab = true) {
    const [skills, integrations, files, svc, share] = await Promise.all([api('/skills'), api('/integrations'), api('/file-workflows').catch(() => ({ workflows: [] })),
      api('/services').catch(() => ({ services: [] })), api('/sharing').catch(() => null)]);
    let counts = data?.counts;
    if (!counts) { try { counts = (await api('/catalog?kind=skills&offset=0&q=')).counts; } catch {} }
    data = { skills, integrations: integrations.integrations, redirect: integrations.redirect_uri, toolsOn: integrations.tools_enabled, fileWorkflows: files.workflows || [], services: svc.services || [], sharing: share, counts: { skills: counts?.skills || 0, connectors: counts?.connectors || 0 } };
    if (keepTab) {
      if ($('#ext-tabs')) { drawTabs(); draw(); }
      if (mounted) paint();
    }
  }
  function bind(scope) {
    (scope.matches?.('.ext-card') ? [scope] : scope.querySelectorAll('.ext-card')).forEach((el) => {
      const key = el.dataset.key, item = current.find((i) => i.key === key); if (!item) return;
      el.querySelector('.ext-main').onclick = () => toggle(key);
      el.querySelector('[data-toggle]').onclick = () => toggle(key);
      const act = el.querySelector('[data-act]'); if (act) act.onclick = safe(() => run(item, act.dataset.act, act));
      el.querySelector('[data-act-install]')?.addEventListener('click', safe((e) => run(item, 'install', e.currentTarget)));
      el.querySelector('[data-act-files]')?.addEventListener('click', () => window.openFileWorkflows?.());
      const instr = el.querySelector('[data-instructions]');
      if (instr) instr.ontoggle = safe(async () => { if (!instr.open || instr.dataset.loaded) return; const out = instr.querySelector('div'); out.textContent = 'Loading…'; const r = await api('/skills/' + encodeURIComponent(instr.dataset.instructions)); out.innerHTML = markdown(r.instructions); instr.dataset.loaded = '1'; });
      el.querySelector('[data-skill-toggle]')?.addEventListener('change', safe(async (e) => { await api('/skills/' + e.target.dataset.skillToggle + '/toggle', 'POST', { enabled: e.target.checked }); item.raw.enabled = e.target.checked; await reload(); }));
      el.querySelector('[data-use]')?.addEventListener('click', (e) => useSkill(e.currentTarget.dataset.use));
      el.querySelector('[data-remove-skill]')?.addEventListener('click', safe(async (e) => { if (!confirm('Remove the skill ' + e.currentTarget.dataset.removeSkill + '?')) return; await api('/skills/' + e.currentTarget.dataset.removeSkill, 'DELETE'); toast('Skill removed'); openKey = ''; await reload(); }));
      el.querySelector('[data-remove-connector]')?.addEventListener('click', safe(async (e) => { if (!confirm('Remove the ' + e.currentTarget.dataset.removeConnector + ' connector?')) return; await api('/connectors/' + e.currentTarget.dataset.removeConnector, 'DELETE'); openKey = ''; await refresh(); await reload(); }));
      el.querySelector('[data-disconnect]')?.addEventListener('click', safe(async (e) => { if (!confirm('Disconnect and delete its saved sign-in from this PC?')) return; await api('/integrations/' + e.currentTarget.dataset.disconnect, 'DELETE'); toast('Disconnected'); await reload(); }));
      el.querySelector('[data-delete-auto]')?.addEventListener('click', safe(async (e) => { if (!confirm('Delete this automation?')) return; await api('/schedules/' + e.currentTarget.dataset.deleteAuto, 'DELETE'); openKey = ''; await refresh(); await reload(); }));
      el.querySelectorAll('[data-copy]').forEach((b) => b.onclick = safe(async () => { await navigator.clipboard.writeText(b.dataset.copy); toast('Copied'); }));
      const service = el.querySelector('form[data-service]');
      if (service) service.onsubmit = safe(async (e) => {
        e.preventDefault(); const id = service.dataset.service, b = Object.fromEntries(new FormData(service)); b.readonly = !!service.elements.readonly?.checked;
        const btn = service.querySelector('.btn.primary'); btn.disabled = true; btn.textContent = 'Connecting…';
        try { await api('/integrations/' + id, 'POST', b); toast(data.integrations.find((i) => i.id === id).auth === 'oauth' ? 'Finish signing in in your browser' : 'Connecting…'); watch(); }
        finally { btn.disabled = false; }
      });
      const autoForm = el.querySelector('#auto-form');
      if (autoForm) autoForm.onsubmit = safe(async (e) => { e.preventDefault(); await api('/schedules', 'POST', Object.fromEntries(new FormData(autoForm))); toast('Automation created'); openKey = ''; await refresh(); await reload(); });
      const skillForm = el.querySelector('#skill-form'), skillFile = el.querySelector('#skill-file');
      if (skillFile) skillFile.onchange = safe(async (e) => { const f = e.target.files[0]; if (!f) return; if (f.size > 20000) throw Error('Skills are limited to 20,000 characters'); skillForm.elements.content.value = await f.text(); if (!skillForm.elements.name.value) skillForm.elements.name.value = f.name.replace(/\.md$/i, '').toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60); });
      if (skillForm) skillForm.onsubmit = safe(async (e) => { e.preventDefault(); await api('/skills', 'POST', Object.fromEntries(new FormData(skillForm))); toast('Skill saved'); openKey = ''; await reload(); });
      el.querySelectorAll('[data-preset]').forEach((b) => b.onclick = () => { const f = el.querySelector('#svc-form'); f.elements.url.value = b.dataset.preset; if (!f.elements.name.value) f.elements.name.value = b.dataset.presetName; f.elements.key.focus(); });
      const svc = el.querySelector('#svc-form');
      if (svc) svc.onsubmit = safe(async (e) => { e.preventDefault(); const b = Object.fromEntries(new FormData(svc)); b.files = svc.elements.files.checked; const btn = svc.querySelector('.btn.primary'); btn.disabled = true; btn.textContent = 'Connecting…'; try { const r = await api('/services', 'POST', b); toast(r.enabled.length ? `Connected ${r.name}: ${r.models.length} models` : `Connected ${r.name}. It lists ${r.models.length} models: tick the ones to use.`); openKey = r.enabled.length ? '' : 'svc:' + r.id; await refresh(); await reload(); } finally { btn.disabled = false; btn.textContent = 'Connect'; } });
      el.querySelector('[data-svc-files]')?.addEventListener('change', safe(async (e) => { await api('/services/' + e.target.dataset.svcFiles + '/files', 'POST', { files: e.target.checked }); await reload(); }));
      el.querySelector('[data-svc-filter]')?.addEventListener('input', (e) => { const q = e.target.value.toLowerCase(); el.querySelectorAll('.svc-model').forEach((row) => { row.hidden = !row.textContent.toLowerCase().includes(q); }); });
      el.querySelector('[data-save-models]')?.addEventListener('click', safe(async (e) => { const sid = e.currentTarget.dataset.saveModels; const ids = [...el.querySelectorAll(`[data-svc-models="${CSS.escape(sid)}"] input:checked`)].map((i) => i.value); const r = await api('/services/' + sid + '/models', 'POST', { enabled: ids }); toast(`${r.enabled.length} models in use`); await refresh(); await reload(); }));
      el.querySelector('[data-refresh-svc]')?.addEventListener('click', safe(async (e) => { const r = await api('/services/' + e.currentTarget.dataset.refreshSvc + '/refresh', 'POST', {}); toast(`${r.models.length} models listed`); await reload(); }));
      el.querySelector('[data-remove-svc]')?.addEventListener('click', safe(async (e) => { if (!confirm('Remove this model service and its saved key?')) return; await api('/services/' + e.currentTarget.dataset.removeSvc, 'DELETE'); openKey = ''; await refresh(); await reload(); }));
      el.querySelector('[data-share]')?.addEventListener('change', safe(async (e) => { await api('/sharing', 'POST', { share_models: e.target.checked }); await reload(); }));
      el.querySelector('[data-new-code]')?.addEventListener('click', safe(async () => { await api('/sharing/code', 'POST', {}); await reload(); }));
      el.querySelector('[data-split]')?.addEventListener('change', safe(async (e) => { const r = await api('/sharing/split', 'POST', { on: e.target.checked }); if (r.problems.length) toast(r.problems.join(' · '), true); else toast(e.target.checked ? `Big models now split across ${r.peers.length + 1} PCs` : 'Back to this PC only'); await reload(); }));
      el.querySelector('[data-find-pcs]')?.addEventListener('click', safe(async (e) => { const out = el.querySelector('[data-found-pcs]'); e.currentTarget.disabled = true; out.innerHTML = '<p class="small-note" role="status">Looking…</p>';
        try { const r = await api('/sharing/find', 'POST', {}); out.innerHTML = r.pcs.length ? r.pcs.map((pc) => `<button type="button" class="btn" data-pick-pc="${esc(pc.address)}">${esc(pc.name)} · ${esc(pc.address)}${pc.pairing ? '' : ' (pairing off)'}</button>`).join(' ') : '<p class="small-note">No PCs found. Check that Luminaria is open there with pairing on, or type its address below.</p>';
          out.querySelectorAll('[data-pick-pc]').forEach((b) => b.onclick = () => { const f = el.querySelector('#pair-form'); f.elements.address.value = b.dataset.pickPc; f.elements.code.focus(); }); } finally { e.currentTarget.disabled = false; } }));
      const pairForm = el.querySelector('#pair-form');
      if (pairForm) pairForm.onsubmit = safe(async (e) => { e.preventDefault(); const btn = pairForm.querySelector('.btn.primary'); btn.disabled = true; btn.textContent = 'Pairing…';
        try { const r = await api('/sharing/pair', 'POST', { address: pairForm.elements.address.value, code: pairForm.elements.code.value }); toast(`Paired with ${r.name}: ${r.models.length} models`); openKey = ''; await refresh(); await reload(); } finally { btn.disabled = false; btn.textContent = 'Pair'; } });
      const mcp = el.querySelector('#mcp-form');
      if (mcp) mcp.onsubmit = safe(async (e) => { e.preventDefault(); const b = Object.fromEntries(new FormData(mcp)); try { b.args = JSON.parse(b.args); } catch { throw Error('Arguments must be a JSON list, for example ["serve"]'); } await api('/connectors', 'POST', b); toast('Connector saved and starting'); openKey = ''; await refresh(); await reload(); });
    });
    scope.querySelectorAll?.('[data-goto]').forEach((b) => b.onclick = safe(async () => {
      const [where, target] = b.dataset.goto.split(/:(.*)/s);
      if (where === 'settings') { closePanel(); window.studioSettingsCategory = target; try { await openPanel('settings'); } finally { window.studioSettingsCategory = null; } return; }
      if (where === 'service') { tab = 'connectors'; openKey = 'service:' + target; drawTabs(); draw(); document.querySelector(`.ext-card[data-key="service:${CSS.escape(target)}"]`)?.scrollIntoView({ block: 'start' }); return; }
      if (where === 'tab') { tab = target; openKey = ''; drawTabs(); draw(); }
    }));
    scope.querySelectorAll?.('[data-goto-browse]').forEach((b) => b.onclick = () => { browseKind = b.dataset.gotoBrowse; tab = 'browse'; drawTabs(); draw(); });
  }
  function useSkill(name) { closePanel(); $('#prompt').value = '/skill ' + name + ' '; $('#prompt').focus(); }
  async function run(item, act, button) {
    if (act === 'open') return toggle(item.key, item.key);
    if (act === 'use-skill') return useSkill(item.raw.name);
    if (act === 'open-files') return window.openFileWorkflows?.();
    if (act === 'toggle-auto') { await api('/schedules/' + item.raw.id, 'PATCH', { enabled: !item.raw.enabled }); await refresh(); await reload(); return; }
    if (act === 'install') {
      const s = item.raw, isSkill = s.kind === 'skill';
      if (!confirm(isSkill ? 'Install ' + item.name + '?\n\nSkills are instructions Luminaria follows. A skill from a stranger can steer it, so read what you install.' : 'Install ' + item.name + '?\n\nThis downloads and runs code from its maker on your PC (' + s.id + '). Only install connectors you trust.')) return;
      button.disabled = true; button.textContent = 'Installing…';
      try {
        if (item.repoSkill) await api('/marketplace/skills/install', 'POST', { repo: item.repoSkill.repo, path: item.repoSkill.path });
        else await api('/catalog/install', 'POST', { id: s.id, confirm: true });
        s.installed = true; Object.assign(item, catalogItem(s), item.repoSkill ? { repoSkill: item.repoSkill } : {}); toast('Installed');
        refresh?.(); await reload(false); rerenderCard(item.key);
      } catch (error) { button.disabled = false; button.textContent = 'Install'; throw error; }
    }
  }
  function watch() {
    clearTimeout(poll); let tries = 0;
    const tick = async () => {
      if (!$('#ext-root') || tries++ > 40) return;
      const before = JSON.stringify(data.integrations.map((i) => [i.id, i.connected, i.status]));
      await reload(false);
      if (JSON.stringify(data.integrations.map((i) => [i.id, i.connected, i.status])) !== before && !document.querySelector('.ext-form :focus')) { drawTabs(); draw(); }
      if (data.integrations.some((i) => i.configured && !i.connected && !/error|failed|denied|timed out|cancel/i.test(i.status || ''))) poll = setTimeout(tick, 3000);
    };
    poll = setTimeout(tick, 2000);
  }
  function counts() {
    const s = skillItems(), c = connectorItems(), w = workflowItems();
    return { installed: s.filter((i) => i.installed).length + c.filter((i) => i.installed).length + w.filter((i) => i.installed).length, skills: s.length, connectors: c.filter((i) => i.installed).length, workflows: (state.schedules || []).length, browse: '' };
  }
  function drawTabs() {
    const n = counts();
    $('#ext-tabs').innerHTML = TABS.map(([id, label]) => `<button type="button" role="tab" id="tab-${id}" aria-selected="${tab === id}" aria-controls="ext-root" data-tab="${id}">${label}${n[id] !== '' && n[id] !== undefined ? ` <span class="count">${n[id]}</span>` : ''}</button>`).join('');
    $$('#ext-tabs [data-tab]').forEach((b) => b.onclick = () => { tab = b.dataset.tab; openKey = ''; drawTabs(); draw(); $('#tab-' + tab)?.focus(); });
    $('#ext-tabs').onkeydown = (e) => { if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return; const i = TABS.findIndex(([id]) => id === tab), next = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length][0]; tab = next; openKey = ''; drawTabs(); draw(); $('#tab-' + tab).focus(); };
  }

  // Settings pages (Model services, Paired PCs) use the same cards and behaviour as the hub.
  let mounted = null;
  function paint() {
    if (!mounted || !mounted.el.isConnected) { mounted = null; return; }
    current = mounted.which === 'services' ? serviceItems() : pcItems();
    mounted.el.innerHTML = current.map(card).join('') || '<p class="note">Nothing here yet.</p>';
    bind(mounted.el);
  }
  window.mountExtensionPage = async function (el, which) {
    mounted = { el, which }; openKey = '';
    el.innerHTML = '<p class="note" role="status">Loading…</p>';
    await reload(false); paint();
  };

  window.openExtensions = async function (startTab, kind) {
    if (startTab) tab = startTab; if (kind) browseKind = kind; openKey = ''; query = '';
    showPanel('Extensions', 'Skills teach Luminaria how to do things. Connectors let it use other apps. Workflows run on their own.',
      `<div class="ext-top"><div class="ext-tabs" id="ext-tabs" role="tablist" aria-label="Extensions"></div><input type="search" id="ext-search" class="filter-input ext-search" placeholder="Search extensions…" aria-label="Search extensions"></div>
       <p class="ext-note" id="ext-note" hidden></p><div id="ext-root" role="tabpanel" aria-live="polite"><p class="note" role="status">Loading…</p></div>`);
    $('.sheet')?.classList.remove('settings-sheet'); $('.sheet')?.classList.add('ext-sheet');
    let t; $('#ext-search').oninput = (e) => { query = e.target.value.trim(); clearTimeout(t); t = setTimeout(() => draw(), tab === 'browse' ? 350 : 0); };
    await reload();
    if (!data.toolsOn) { const note = $('#ext-note'); note.hidden = false; note.innerHTML = 'Connectors can sign in now, but their tools only run after you turn on <strong>Computer and command tools</strong> in Settings › Permissions, or choose Full access.'; }
  };

  // Old entry points open the hub on the matching tab.
  const ROUTES = { extensions: ['installed'], skills: ['skills'], integrations: ['connectors'], schedules: ['workflows'], marketplace: ['browse'] };
  const original = openPanel;
  openPanel = async function (name) { if (ROUTES[name]) return window.openExtensions(...ROUTES[name]); $('.sheet')?.classList.remove('ext-sheet'); return original(name); };
})();

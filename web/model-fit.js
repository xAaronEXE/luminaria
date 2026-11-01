// Fit ratings in the model library: how each model should run on *this* PC,
// one-click recommended load settings, a smart benchmark, and manual tuning.
// settings.js renders the markup through LuminariaFit; handlers bind here.
(() => {
  const GB = 1024 ** 3;
  const html = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const gb = (n) => (n == null ? '—' : (n / GB).toFixed(n >= 10 * GB ? 0 : 1) + ' GB');
  const tokens = (n) => (n >= 1024 ? Math.round(n / 1024) + 'k' : String(n));
  const ICON = {
    recommended: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.5l1.9 4 4.3.5-3.2 2.9.9 4.3L8 11l-3.9 2.2.9-4.3L1.8 6l4.3-.5z" fill="currentColor"/></svg>',
    good: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    slow: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 4.5V8l2.4 1.6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    unstable: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.8l6.6 11.7H1.4z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M8 6.2v3.4M8 11.6v.1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    too_large: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M4 12L12 4" stroke="currentColor" stroke-width="1.6"/></svg>',
    unknown: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6.3 6.3a1.8 1.8 0 113 1.4c-.8.5-1.3.9-1.3 1.8M8 11.6v.1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>'
  };

  function badge(fit, compact) {
    if (!fit) return '';
    const title = fit.meaning ? ` title="${html(fit.label + ': ' + fit.meaning)}"` : '';
    return `<span class="fit-badge fit-${fit.rating}${compact ? ' compact' : ''}"${title}>${ICON[fit.rating] || ''}<span>${html(fit.label)}</span></span>`;
  }

  function dot(item) {
    if (!item.fit) return '';
    return `<span class="fit-dot fit-${item.fit.rating}" title="${html(item.fit.label)}" aria-label="${html(item.fit.label)} on this PC"></span>${item.best_fit ? '<span class="best-fit">Best fit</span>' : ''}`;
  }

  function meter(label, used, total) {
    if (!total || used == null) return '';
    const share = Math.min(100, Math.round((used / total) * 100));
    return `<div class="fit-meter"><div class="fit-meter-label"><span>${label}</span><span>${gb(used)} of ${gb(total)}</span></div><div class="fit-meter-bar" role="img" aria-label="${label}: ${share}% used"><span style="width:${share}%"></span></div></div>`;
  }

  function panel(model, quant) {
    const fit = quant.fit;
    if (!fit) return '';
    const machine = window.studioMachine || {};
    const installed = quant.installed && quant.registered;
    const s = fit.settings || {};
    const custom = quant.launch && Object.keys(quant.launch).length;
    const moe = !!model.active_parameters;
    const contexts = [8192, 16384, 32768, 40960, 65536, 131072].filter((c) => !model.context_supported || c <= model.context_supported);
    const currentContext = quant.context || s.context;
    const form = installed ? `
      <form class="fit-custom" data-fit-form hidden>
        <label><span>Context</span><select name="context">${contexts.map((c) => `<option value="${c}" ${c === currentContext ? 'selected' : ''}>${tokens(c)} tokens</option>`).join('')}</select><small>How much conversation it can see at once. More uses more memory.</small></label>
        <label><span>Layers on the GPU</span><input name="gpu_layers" type="number" min="-1" max="512" step="1" value="${quant.launch?.gpu_layers ?? s.gpu_layers ?? -1}"><small>-1 puts every layer on the GPU. Fewer layers free graphics memory but run slower.</small></label>
        ${moe ? `<label><span>Expert layers on the CPU</span><input name="cpu_moe" type="number" min="0" max="256" step="1" value="${quant.launch?.cpu_moe ?? s.cpu_moe ?? 0}"><small>Moves this many layers' experts to system memory. Lower is faster if it still fits.</small></label>` : ''}
        <label><span>Prompt batch size</span><select name="ubatch">${[128, 256, 512, 1024].map((b) => `<option value="${b}" ${b === (quant.launch?.ubatch ?? s.ubatch ?? 512) ? 'selected' : ''}>${b}</option>`).join('')}</select><small>Larger reads long files and tool output faster but needs more graphics memory.</small></label>
        <div class="fit-form-actions"><button class="btn primary" type="submit">Save and reload</button><button class="btn" type="button" data-fit-auto>Back to automatic</button></div>
      </form>` : '';
    const actions = installed ? `
      <div class="fit-actions">
        <button class="btn primary" type="button" data-fit-apply>Use recommended settings</button>
        <button class="btn" type="button" data-fit-tune>Find best settings</button>
        <button class="btn quiet" type="button" data-fit-adjust aria-expanded="false">Adjust</button>
      </div>` : '';
    const recommended = [s.context && `${tokens(s.context)} context`,
      s.gpu_layers === -1 ? 'all layers on GPU' : s.gpu_layers ? `${s.gpu_layers} layers on GPU` : s.gpu_layers === 0 ? 'CPU only' : '',
      s.cpu_moe ? `${s.cpu_moe} expert layers on CPU` : ''].filter(Boolean).join(' · ');
    return `<section class="fit-panel fit-${fit.rating}" data-fit-panel data-model="${html(quant.registry_id)}" data-settings='${html(JSON.stringify(s))}'>
      <div class="fit-head">${badge(fit)}<span class="fit-source">${html(fit.note)}</span>${custom ? '<span class="fit-custom-flag">Custom settings</span>' : ''}</div>
      <p class="fit-meaning">${html(fit.meaning)}</p>
      ${fit.detail ? `<p class="fit-detail">${html(fit.detail)}</p>` : ''}
      ${fit.model_limit ? `<p class="fit-model-limit" role="note">${html(fit.model_limit)}</p>` : ''}
      <div class="fit-meters">${meter('Graphics memory', fit.vram_used, machine.vram_total)}${fit.ram_used ? meter('System memory', fit.ram_used, machine.ram_total) : ''}</div>
      ${recommended ? `<p class="fit-suggested"><span>Recommended for this PC</span>${html(recommended)}</p>` : ''}
      ${actions}${form}
      <p class="fit-status" role="status" aria-live="polite"></p>
    </section>`;
  }

  function machineStrip(machine) {
    if (!machine) return '';
    const gpu = machine.integrated ? `${html(machine.gpu || 'Integrated graphics')} (shares system memory)` : machine.vram_total ? `${html(machine.gpu || 'Graphics card')} · ${gb(machine.vram_total)} graphics memory` : machine.source ? 'No dedicated graphics card found' : 'Graphics memory not detected';
    const source = machine.source === 'you' ? 'Set by you' : machine.source === 'llama.cpp' ? 'Detected by the model runtime' : machine.source === 'driver' ? 'Detected from the driver' : 'Not detected';
    return `<div class="fit-machine-main"><span class="fit-machine-label">This PC</span><strong>${gpu}</strong><span>${gb(machine.ram_total)} system memory</span><small>${source}. Ratings are estimates; results vary by driver, settings and other open apps.</small></div>
      <div class="fit-machine-actions"><button class="btn quiet" type="button" data-machine-edit aria-expanded="false">Correct this</button><button class="btn quiet" type="button" data-machine-detect>Detect again</button></div>
      <form class="fit-machine-form" data-machine-form hidden><label><span>Graphics memory (GB)</span><input name="vram_gb" type="number" min="0" max="512" step="0.5" value="${machine.vram_total ? (machine.vram_total / GB).toFixed(1) : ''}" required></label><label class="fit-check"><input type="checkbox" name="integrated" ${machine.integrated ? 'checked' : ''}><span>Integrated graphics (shares system memory)</span></label><button class="btn primary" type="submit">Save</button><button class="btn" type="button" data-machine-auto>Use detection</button></form>`;
  }

  async function reloadLibrary() {
    // Re-open the Models page so every rating is recalculated.
    const nav = [...document.querySelectorAll('.settings-nav button, .settings-navigation button')].find((b) => /model library|models/i.test(b.textContent));
    if (nav) nav.click();
  }

  function bindPanel(section) {
    if (section.dataset.bound) return;
    section.dataset.bound = '1';
    const id = section.dataset.model;
    const status = section.querySelector('.fit-status');
    const say = (text, bad) => { status.textContent = text; status.classList.toggle('bad', !!bad); };
    const settings = JSON.parse(section.dataset.settings || '{}');
    const save = async (body, done) => {
      section.querySelectorAll('button').forEach((b) => (b.disabled = true));
      say('Saving and reloading the model…');
      try {
        const result = await api('/models/' + encodeURIComponent(id) + '/launch', 'POST', body);
        say(done || result.message || 'Saved.');
        setTimeout(reloadLibrary, 900);
      } catch (error) { say(error.message || 'Could not save these settings.', true); }
      finally { section.querySelectorAll('button').forEach((b) => (b.disabled = false)); }
    };
    section.querySelector('[data-fit-apply]')?.addEventListener('click', () => save({
      context: settings.context, gpu_layers: settings.gpu_layers, cpu_moe: settings.cpu_moe || undefined, ubatch: settings.ubatch
    }, 'Recommended settings saved. The model reloads on its next request.'));
    section.querySelector('[data-fit-tune]')?.addEventListener('click', async (event) => {
      event.target.disabled = true;
      say('Measuring a few settings around the recommendation. This loads the model several times and can take a few minutes…');
      try {
        await api('/tuning/start', 'POST', { model: id, consent: true, smart: true });
        say('Benchmark running. Results appear in Settings › Hardware & tuning, where you can apply the fastest one.');
      } catch (error) { say(error.message || 'Could not start the benchmark.', true); event.target.disabled = false; }
    });
    const adjust = section.querySelector('[data-fit-adjust]');
    const form = section.querySelector('[data-fit-form]');
    adjust?.addEventListener('click', () => { form.hidden = !form.hidden; adjust.setAttribute('aria-expanded', String(!form.hidden)); });
    form?.addEventListener('submit', (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const body = { context: Number(data.get('context')), gpu_layers: Number(data.get('gpu_layers')), ubatch: Number(data.get('ubatch')) };
      if (data.has('cpu_moe')) body.cpu_moe = Number(data.get('cpu_moe'));
      save(body);
    });
    section.querySelector('[data-fit-auto]')?.addEventListener('click', () => save({ mode: 'auto' }, 'Back to automatic. llama.cpp fits the model itself on the next load.'));
  }

  function bindMachine(strip) {
    if (strip.dataset.bound) return;
    strip.dataset.bound = '1';
    const form = strip.querySelector('[data-machine-form]');
    const edit = strip.querySelector('[data-machine-edit]');
    const post = async (body) => {
      try { await api('/hardware/profile', 'POST', body); reloadLibrary(); }
      catch (error) { if (typeof toast === 'function') toast(error.message); }
    };
    edit.addEventListener('click', () => { form.hidden = !form.hidden; edit.setAttribute('aria-expanded', String(!form.hidden)); });
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const data = new FormData(form);
      post({ vram_gb: Number(data.get('vram_gb')), integrated: data.get('integrated') === 'on' });
    });
    strip.querySelector('[data-machine-auto]').addEventListener('click', () => post({ auto: true }));
    strip.querySelector('[data-machine-detect]').addEventListener('click', async (event) => {
      event.target.disabled = true; event.target.textContent = 'Detecting…';
      try { await api('/hardware/profile?refresh=true'); reloadLibrary(); }
      catch (error) { event.target.disabled = false; event.target.textContent = 'Detect again'; }
    });
  }

  function scan() {
    document.querySelectorAll('[data-fit-panel]').forEach(bindPanel);
    const strip = document.getElementById('fit-machine');
    if (strip && window.studioMachine && !strip.dataset.rendered) {
      strip.dataset.rendered = '1';
      strip.innerHTML = machineStrip(window.studioMachine);
      bindMachine(strip);
    }
  }
  new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });

  window.LuminariaFit = { badge, dot, panel, machineStrip };
})();

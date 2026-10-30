// Aurora glass: keeps the visual effects in step with the user's motion
// preference and the PC's capability, and swaps a few dropdowns for
// plain choice cards. Pure presentation; no API calls of its own.
(() => {
  const body = document.body;

  // 'full' or 'low' forces a level; anything else = decide automatically.
  let forced = '';
  try { forced = localStorage.getItem('luminaria-effects') || ''; } catch {}
  const cores = navigator.hardwareConcurrency || 8;
  const memory = navigator.deviceMemory || 8;
  body.classList.toggle('effects-low', forced === 'low' || (forced !== 'full' && (cores <= 4 || memory <= 4)));

  // Follow the app's own Motion preference (Settings > Appearance).
  window.addEventListener('studio-preferences', (event) => {
    body.classList.toggle('motion-off', (event.detail || {}).motion === false);
  });

  // Dropdowns that read better as two or three big, obvious choices.
  // The original <select> stays in the page (hidden) so existing save
  // handlers keep reading its value unchanged.
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
    const sync = () => {
      for (const card of group.children) card.setAttribute('aria-checked', String(card.dataset.value === select.value));
    };
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
  }

  new MutationObserver(enhance).observe(document.body, { childList: true, subtree: true });
  enhance();
})();

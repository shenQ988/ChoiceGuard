(() => {
  if (globalThis.__choiceGuardInstalled) return;
  globalThis.__choiceGuardInstalled = true;
  let flagged = new Set(), goal = '', sequence = 0, generation = 0;
  let controls = new Map();
  const bypass = new WeakSet();
  let recentActions = [];
  const historyKey = '__choiceguard_recent_actions';
  try {
    recentActions = JSON.parse(sessionStorage.getItem(historyKey) || '[]')
      .filter(a => typeof a.label === 'string' && Date.now() - a.time < 600000).slice(-5);
  } catch (_) { recentActions = []; }
  // Capture only control labels after activation; never typed field values.
  function remember(control) {
    const label = (control.innerText || control.getAttribute('aria-label') || control.value || '').trim().slice(0, 200);
    if (!label) return;
    recentActions.push({label, time: Date.now()});
    recentActions = recentActions.slice(-5);
    try { sessionStorage.setItem(historyKey, JSON.stringify(recentActions)); } catch (_) {}
  }
  let dialogOpen = false;
  function clear() { flagged.clear(); generation++; }
  // Invalidate stale analysis when the page changes. Reanalyze explicitly.
  const observer = new MutationObserver(clear);
  const observe = () => observer.observe(document.documentElement, {
    subtree: true, childList: true, characterData: true,
    attributes: true, attributeFilter: ['href', 'disabled', 'aria-label', 'value']
  });
  observe();
  function warn(control) {
    if (dialogOpen) return;
    dialogOpen = true;
    observer.disconnect();
    const host = document.createElement('div');
    const shadow = host.attachShadow({mode: 'closed'});
    const dialog = document.createElement('dialog');
    const style = document.createElement('style');
    style.textContent = 'dialog{font:16px system-ui;max-width:420px;border:0;border-radius:16px;padding:28px;box-shadow:0 20px 80px #0006}dialog::backdrop{background:#0008}button{padding:10px 16px;margin:8px 8px 0 0;cursor:pointer}p{line-height:1.5}';
    const title = document.createElement('h2'); title.textContent = 'Check your choice';
    const text = document.createElement('p');
    text.textContent = `Your analyzed goal: ${goal}. “${control.innerText || control.value || control.getAttribute('aria-label')}” appears to conflict with it.`;
    const back = document.createElement('button'); back.textContent = 'Go back';
    const proceed = document.createElement('button'); proceed.textContent = 'Proceed anyway';
    const close = () => { dialog.close(); host.remove(); dialogOpen = false; observe(); control.focus(); };
    back.onclick = close;
    proceed.onclick = () => { close(); bypass.add(control); try { control.click(); } finally { bypass.delete(control); } };
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    dialog.append(title, text, back, proceed); shadow.append(style, dialog);
    document.documentElement.append(host); dialog.showModal(); back.focus();
  }
  document.addEventListener('click', event => {
    const node = event.target instanceof Element ? event.target.closest('[data-choiceguard-id]') : null;
    if (!node || bypass.has(node) || controls.get(node.dataset.choiceguardId) !== node) return;
    if (flagged.has(node.dataset.choiceguardId)) {
      event.preventDefault(); event.stopImmediatePropagation(); warn(node);
    } else { remember(node); }
  }, true);
  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (message.type !== 'START_ANALYSIS') return;
    (async () => {
      clear(); controls = new Map();
      const buttons = [...document.querySelectorAll('button,a[href],input[type=submit],input[type=button],[role=button]')]
        .filter(e => e.getClientRects().length && !e.disabled).slice(0, 150).map(e => {
          const id = `cg-${++sequence}`; e.dataset.choiceguardId = id; controls.set(id, e);
          return {id, text: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim().slice(0, 500)};
        });
      const version = generation, url = location.href;
      const result = await chrome.runtime.sendMessage({type: 'ANALYZE', page: {
        url, mode: !message.useApi && !(message.userGoal || '').trim() && url === 'http://127.0.0.1:8765/demo' ? 'demo' : 'api',
        headings: [...document.querySelectorAll('h1,h2,[role=heading]')].filter(e => e.getClientRects().length).slice(0,20).map(e => e.innerText.slice(0,300)),
        recent_actions: recentActions.filter(a => Date.now() - a.time < 600000),
        user_goal: (message.userGoal || '').slice(0, 500), title: document.title, text: document.body.innerText.slice(0, 30000), buttons
      }});
      if (!result.ok) throw new Error(result.error);
      if (version !== generation || url !== location.href) throw new Error('Page changed during analysis. Analyze again.');
      flagged = new Set(result.data.conflicting_button_ids.filter(id => controls.has(id)));
      goal = result.data.goal.description;
      const evidence = (result.data.goal.evidence || []).join('; ');
      const summary = result.data.goal.status === 'unclear'
        ? ((message.userGoal || '').trim() ? 'Could not interpret your goal using the supported states. No warnings enabled; try more specific wording.' : 'Goal uncertain: no warnings enabled. Enter your goal in ChoiceGuard and analyze again.')
        : `${flagged.size} conflicting control(s). ${flagged.size ? 'Click warnings enabled until the page changes.' : 'No controls flagged; no click warnings enabled.'}`;
      respond({ok: true, message: `Goal (${result.data.goal.status}): ${goal}\n${evidence ? 'Evidence: ' + evidence + '\n' : ''}${summary}`});
    })().catch(error => respond({ok: false, error: error.message}));
    return true;
  });
})();

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message.type !== 'ANALYZE') return;
  if (sender.id !== chrome.runtime.id) return;
  fetch('http://127.0.0.1:8765/analyze', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(message.page), signal: AbortSignal.timeout(60000)
  }).then(async response => {
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Analysis failed');
    respond({ok: true, data});
  }).catch(error => {
    const message = error.name === 'TimeoutError' || error.name === 'AbortError'
      ? 'Analysis timed out. Check the backend terminal and try again.'
      : error instanceof TypeError
        ? 'Cannot connect to the local ChoiceGuard backend. In the project terminal run: python3 backend/server.py. Keep that terminal running, then retry.'
        : error.message;
    respond({ok: false, error: message});
  });
  return true;
});

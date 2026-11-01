document.getElementById('analyze').onclick = async () => {
  const status = document.getElementById('status');
  status.textContent = 'Analyzing…';
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['content.js']});
    const result = await chrome.tabs.sendMessage(tab.id, {type: 'START_ANALYSIS', useApi: !document.getElementById('api').checked, userGoal: document.getElementById('goal').value.trim()});
    status.textContent = result.ok ? result.message : result.error;
  } catch (error) { status.textContent = error.message; }
};

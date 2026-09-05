const BACKEND_URL = "http://127.0.0.1:8000/api/v1/audit";

async function getPagePayload(tabId) {
  const tabs = await chrome.tabs.sendMessage(tabId, {type: "COLLECT_RESPONSE"}).catch(() => null);
  if (tabs) return tabs;
  await chrome.scripting.executeScript({target: {tabId}, files: ["src/content.js"]});
  return chrome.tabs.sendMessage(tabId, {type: "COLLECT_RESPONSE"});
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "AUDIT_ACTIVE_TAB") return false;
  (async () => {
    try {
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      if (!tab || !tab.id) throw new Error("No active tab is available.");
      const payload = await getPagePayload(tab.id);
      const response = await fetch(BACKEND_URL, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}. Is it running?`);
      const result = await response.json();
      await chrome.tabs.sendMessage(tab.id, {type: "HIGHLIGHT_RESULTS", results: result.citations}).catch(() => {});
      sendResponse({ok: true, result});
    } catch (error) {
      sendResponse({ok: false, error: error.message || String(error)});
    }
  })();
  return true;
});


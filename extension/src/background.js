const BACKEND_URL = "http://127.0.0.1:8000/api/v1/audit";

chrome.sidePanel
  .setPanelBehavior({openPanelOnActionClick: true})
  .catch((error) => console.error("Unable to configure side panel:", error));

async function getPagePayload(tabId) {
  const message = {type: "COLLECT_RESPONSE"};
  const tabs = await chrome.tabs.sendMessage(tabId, message).catch(() => null);
  if (tabs) return tabs;
  await chrome.scripting.executeScript({target: {tabId}, files: ["src/content.js"]});
  return chrome.tabs.sendMessage(tabId, message);
}

const dynamicSelectionTabs = new Map();

chrome.tabs.onRemoved.addListener((tabId) => dynamicSelectionTabs.delete(tabId));

function notifyPanel(message) {
  chrome.runtime.sendMessage(message).catch(() => {});
}

async function setDynamicSelectionMode(tabId, enabled) {
  const message = {type: "SET_DYNAMIC_SELECTION_MODE", enabled};
  const response = await chrome.tabs.sendMessage(tabId, message).catch(() => null);
  if (response) return response;
  await chrome.scripting.executeScript({target: {tabId}, files: ["src/content.js"]});
  return chrome.tabs.sendMessage(tabId, message);
}

async function auditDynamicSelection(tabId, selectionId, payload) {
  const session = dynamicSelectionTabs.get(tabId);
  if (!session?.enabled) return;
  notifyPanel({type: "DYNAMIC_SELECTION_AUDIT_STARTED", tab_id: tabId, selection_id: selectionId});
  try {
    const response = await fetch(BACKEND_URL, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}. Is it running?`);
    const result = await response.json();
    const currentSession = dynamicSelectionTabs.get(tabId);
    if (!currentSession?.enabled) return;
    currentSession.audits.push({selection_id: selectionId, result});
    notifyPanel({type: "DYNAMIC_SELECTION_AUDIT_UPDATED", tab_id: tabId, selection_id: selectionId, result});
    await chrome.tabs.sendMessage(tabId, {type: "HIGHLIGHT_RESULTS", results: result.citations}).catch(() => {});
  } catch (error) {
    notifyPanel({type: "DYNAMIC_SELECTION_AUDIT_ERROR", tab_id: tabId, selection_id: selectionId, error: error.message || String(error)});
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "START_DYNAMIC_SELECTION" || message.type === "STOP_DYNAMIC_SELECTION") {
    (async () => {
      try {
        const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
        if (!tab || typeof tab.id !== "number") throw new Error("No active tab is available.");
        const enabled = message.type === "START_DYNAMIC_SELECTION";
        await setDynamicSelectionMode(tab.id, enabled);
        if (enabled) {
          dynamicSelectionTabs.set(tab.id, {enabled: true, audits: []});
        } else {
          dynamicSelectionTabs.delete(tab.id);
        }
        sendResponse({ok: true, enabled});
      } catch (error) {
        sendResponse({ok: false, error: error.message || String(error)});
      }
    })();
    return true;
  }

  if (message.type === "SELECTION_BLOCK_READY") {
    const tabId = sender.tab?.id;
    if (typeof tabId === "number") auditDynamicSelection(tabId, message.selection_id, message.payload);
    return false;
  }

  if (message.type !== "AUDIT_ACTIVE_TAB") return false;
  (async () => {
    try {
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      if (!tab || !tab.id) throw new Error("No active tab is available.");
      notifyPanel({type: "AUDIT_PROGRESS", phase: "collecting"});
      const payload = await getPagePayload(tab.id);
      notifyPanel({type: "AUDIT_PROGRESS", phase: "sending"});
      const response = await fetch(BACKEND_URL, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}. Is it running?`);
      notifyPanel({type: "AUDIT_PROGRESS", phase: "receiving"});
      const result = await response.json();
      await chrome.tabs.sendMessage(tab.id, {type: "HIGHLIGHT_RESULTS", results: result.citations}).catch(() => {});
      sendResponse({ok: true, result});
    } catch (error) {
      sendResponse({ok: false, error: error.message || String(error)});
    }
  })();
  return true;
});

(() => {
  let lastSelection = null;
  let dynamicSelectionEnabled = false;
  let selectionTimer = null;
  let selectionSequence = 0;
  let lastSubmittedSignature = "";
  const dynamicSelectionRanges = new Map();
  const BLOCK_TAGS = new Set([
    "ARTICLE", "BLOCKQUOTE", "DD", "DIV", "DT", "H1", "H2", "H3", "H4", "H5", "H6",
    "LI", "P", "PRE", "SECTION", "TD", "TH",
  ]);
  const EXCLUDED_SELECTOR = "script, style, template, nav, aside, footer, form, textarea, input, button, [aria-hidden=\"true\"], [data-lauudit-ignore]";

  function visible(element) {
    const style = window.getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
  }

  function nodeText(element) {
    if (!element) return "";
    const value = typeof element.innerText === "string" ? element.innerText : element.textContent || "";
    return value.replaceAll("\r\n", "\n").replaceAll("\u00a0", " ").trim();
  }

  function excluded(element) {
    return Boolean(element?.matches?.(EXCLUDED_SELECTOR) || element?.closest?.(EXCLUDED_SELECTOR));
  }

  function hasBlockDescendant(element) {
    return Array.from(element.children || []).some((child) => {
      if (excluded(child)) return false;
      if (BLOCK_TAGS.has(child.tagName)) return true;
      return hasBlockDescendant(child);
    });
  }

  function contentBlocks(root) {
    const elements = [root, ...Array.from(root.querySelectorAll("*"))];
    const blocks = elements.filter((element) => {
      if (excluded(element) || !visible(element) || !nodeText(element)) return false;
      if (element === root) return !hasBlockDescendant(element);
      return BLOCK_TAGS.has(element.tagName) && !hasBlockDescendant(element);
    });
    return blocks.length ? blocks : [root];
  }

  function rootDescription(element) {
    if (!element) return "none";
    const label = element.getAttribute("aria-label") || element.id || element.className || "";
    return `${element.tagName.toLowerCase()}${label ? `[${String(label).trim().slice(0, 120)}]` : ""}`;
  }

  function rootScore(element) {
    if (!element || excluded(element) || !visible(element)) return -Infinity;
    const text = nodeText(element);
    if (text.length < 40) return -Infinity;
    const label = `${element.id || ""} ${element.className || ""} ${element.getAttribute("aria-label") || ""}`.toLowerCase();
    const penalty = /(source|sources|steps|navigation|sidebar|menu)/.test(label) ? 5000 : 0;
    const bodyPenalty = element === document.body ? 100000 : 0;
    const blocks = contentBlocks(element).length;
    return Math.min(text.length, 50000) + blocks * 100 - penalty - bodyPenalty;
  }

  function chooseResponseRoot() {
    const candidates = [
      ...Array.from(document.querySelectorAll("[data-testid*=response], [data-testid*=answer], [class*=response], [class*=answer], main, article, [role=main]")),
      document.body,
    ].filter((element, index, values) => element && values.indexOf(element) === index);
    const fallback = document.body;
    if (!candidates.length) return fallback;
    return candidates.reduce((best, candidate) => {
      if (!best) return candidate;
      return rootScore(candidate) > rootScore(best) ? candidate : best;
    }, fallback) || fallback;
  }

  function collectPageCapture() {
    const root = chooseResponseRoot();
    const blocks = contentBlocks(root);
    const links = [];
    let responseText = "";
    const structuredBlocks = blocks.map((element, blockIndex) => {
      const text = nodeText(element);
      if (responseText) responseText += "\n\n";
      const start = responseText.length;
      responseText += text;
      const end = responseText.length;
      let linkCursor = 0;
      Array.from(element.querySelectorAll("a[href]"))
        .filter((anchor) => visible(anchor) && !excluded(anchor))
        .forEach((anchor) => {
          const linkText = nodeText(anchor);
          if (!linkText) return;
          const nextStart = text.indexOf(linkText, linkCursor);
          const localStart = nextStart >= 0 ? nextStart : text.indexOf(linkText);
          const offset = localStart >= 0 ? localStart : 0;
          links.push({
            text: linkText,
            href: anchor.href,
            context: text,
            block_id: `block-${blockIndex + 1}`,
            start: start + offset,
            end: start + offset + linkText.length,
          });
          linkCursor = Math.max(linkCursor, offset + linkText.length);
        });
      return {
        id: `block-${blockIndex + 1}`,
        tag: element.tagName.toLowerCase(),
        text,
        start,
        end,
      };
    });
    return {
      response_text: responseText,
      links,
      content_blocks: structuredBlocks,
      capture_diagnostics: {
        root: rootDescription(root),
        fallback_to_body: root === document.body,
        block_count: structuredBlocks.length,
        text_length: responseText.length,
      },
    };
  }

  function collectResponse() {
    const capture = collectPageCapture();
    return {...capture, page_url: location.href, user_query: null, jurisdiction: "Singapore", as_of_date: new Date().toISOString().slice(0, 10)};
  }

  function rememberSelection() {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount || !selection.toString().trim()) return;
    lastSelection = {
      range: selection.getRangeAt(0).cloneRange(),
      text: selection.toString().trim(),
    };
  }

  function currentSelectionRange() {
    const activeSelection = window.getSelection();
    const activeText = activeSelection?.toString().trim() || "";
    if (activeText && activeSelection?.rangeCount) return activeSelection.getRangeAt(0);
    return lastSelection?.range || null;
  }

  function intersects(range, node) {
    try {
      return range.intersectsNode(node);
    } catch (_error) {
      return false;
    }
  }

  function collectSelectedResponse() {
    const activeSelection = window.getSelection();
    const activeText = activeSelection?.toString().trim() || "";
    const range = currentSelectionRange();
    const responseText = activeText || lastSelection?.text || "";
    if (!responseText) return null;

    const links = Array.from(document.querySelectorAll("a[href]"))
      .filter((anchor) => visible(anchor) && range && intersects(range, anchor))
      .map((anchor) => ({
        text: (anchor.innerText || anchor.textContent || "").trim(),
        href: anchor.href,
        context: (anchor.closest("p, li, article, main, section") || anchor.parentElement || document.body).innerText.trim(),
      }))
      .filter((link) => link.text || link.href);
    return {response_text: responseText, links, page_url: location.href, user_query: null, jurisdiction: "Singapore", as_of_date: new Date().toISOString().slice(0, 10)};
  }

  function highlightTone(status) {
    const value = String(status ?? "").trim().toUpperCase();
    if (["VERIFIED_EXISTS", "LIVE_VERIFIED", "SUPPORTED", "LINK_CONFIRMS_CASE"].includes(value)) return "verified";
    if (["UNCERTAIN", "UNABLE_TO_EVALUATE", "AMBIGUOUS_MATCH", "SOURCE_UNAVAILABLE", "NO_LINK_AVAILABLE"].includes(value)) return "uncertain";
    if (value.includes("MISMATCH") || value.includes("NOT_FOUND") || value.includes("UNSUPPORTED") || value.includes("BROKEN") || value.includes("DIFFERENT_CASE") || value.includes("SEARCH_RESULTS")) return "error";
    return "uncertain";
  }

  function clearHighlights() {
    if (!window.CSS?.highlights) return;
    ["lca-verified", "lca-uncertain", "lca-error"].forEach((name) => window.CSS.highlights.delete(name));
  }

  function installHighlightStyles() {
    if (document.getElementById("lauudit-highlight-styles")) return;
    const style = document.createElement("style");
    style.id = "lauudit-highlight-styles";
    style.textContent = `
      ::highlight(lca-verified) { background-color: rgba(34, 197, 94, .35); }
      ::highlight(lca-uncertain) { background-color: rgba(250, 204, 21, .45); }
      ::highlight(lca-error) { background-color: rgba(248, 113, 113, .4); }
      ::highlight(lca-selection) { background-color: rgba(59, 130, 246, .28); }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function findTextRanges(raw) {
    if (!raw || !document.body) return [];
    const ranges = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.nodeValue.trim() || node.parentElement?.closest("script, style, textarea, input, button")) continue;
      let offset = 0;
      while ((offset = node.nodeValue.indexOf(raw, offset)) !== -1) {
        const range = document.createRange();
        range.setStart(node, offset);
        range.setEnd(node, offset + raw.length);
        ranges.push(range);
        offset += raw.length;
      }
    }
    return ranges;
  }

  function highlight(results) {
    clearHighlights();
    if (!window.CSS?.highlights || typeof window.Highlight !== "function") return;
    installHighlightStyles();

    const rangesByTone = new Map([
      ["verified", []],
      ["uncertain", []],
      ["error", []],
    ]);
    const byText = new Map(results.map((item) => [item.raw_text, item.status]));
    byText.forEach((status, raw) => {
      rangesByTone.get(highlightTone(status)).push(...findTextRanges(raw));
    });
    rangesByTone.forEach((ranges, tone) => {
      if (ranges.length) window.CSS.highlights.set(`lca-${tone}`, new window.Highlight(...ranges));
    });
  }

  function renderDynamicSelectionHighlight() {
    if (!window.CSS?.highlights || typeof window.Highlight !== "function") return;
    installHighlightStyles();
    const ranges = Array.from(dynamicSelectionRanges.values()).filter((range) => {
      try {
        return range.collapsed === false;
      } catch (_error) {
        return false;
      }
    });
    if (ranges.length) {
      window.CSS.highlights.set("lca-selection", new window.Highlight(...ranges));
    } else {
      window.CSS.highlights.delete("lca-selection");
    }
  }

  function selectionSignature(payload, range) {
    const container = range?.commonAncestorContainer;
    const element = container?.nodeType === Node.ELEMENT_NODE ? container : container?.parentElement;
    return `${payload.response_text}::${element?.textContent?.slice(0, 120) || ""}:${range?.startOffset || 0}:${range?.endOffset || 0}`;
  }

  function submitDynamicSelection() {
    if (!dynamicSelectionEnabled) return;
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount || !selection.toString().trim()) return;
    const payload = collectSelectedResponse();
    const range = currentSelectionRange();
    if (!payload || !range) return;

    const signature = selectionSignature(payload, range);
    if (signature === lastSubmittedSignature) return;
    lastSubmittedSignature = signature;
    const selectionId = `selection-${Date.now()}-${++selectionSequence}`;
    dynamicSelectionRanges.set(selectionId, range.cloneRange());
    renderDynamicSelectionHighlight();
    chrome.runtime.sendMessage({type: "SELECTION_BLOCK_READY", selection_id: selectionId, payload});
  }

  function setDynamicSelectionMode(enabled) {
    dynamicSelectionEnabled = enabled;
    lastSubmittedSignature = "";
    clearTimeout(selectionTimer);
    selectionTimer = null;
    if (!enabled) {
      dynamicSelectionRanges.clear();
      if (window.CSS?.highlights) window.CSS.highlights.delete("lca-selection");
    } else {
      dynamicSelectionRanges.clear();
      renderDynamicSelectionHighlight();
    }
    return {enabled: dynamicSelectionEnabled};
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === "COLLECT_RESPONSE") {
      sendResponse(collectResponse());
      return true;
    }
    if (message.type === "COLLECT_SELECTED_RESPONSE") {
      const payload = collectSelectedResponse();
      sendResponse(payload ? {ok: true, payload} : {ok: false, error: "Select some response text before auditing."});
      return true;
    }
    if (message.type === "SET_DYNAMIC_SELECTION_MODE") {
      sendResponse(setDynamicSelectionMode(Boolean(message.enabled)));
      return true;
    }
    if (message.type === "HIGHLIGHT_RESULTS") {
      highlight(message.results || []);
      sendResponse({ok: true});
      return true;
    }
  });

  document.addEventListener("selectionchange", () => {
    rememberSelection();
    if (!dynamicSelectionEnabled) return;
    clearTimeout(selectionTimer);
    selectionTimer = setTimeout(submitDynamicSelection, 450);
  });
  document.addEventListener("mouseup", () => {
    if (dynamicSelectionEnabled) setTimeout(submitDynamicSelection, 0);
  });
})();

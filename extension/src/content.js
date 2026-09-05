(() => {
  let lastSelection = null;
  let dynamicSelectionEnabled = false;
  let selectionTimer = null;
  let selectionSequence = 0;
  let lastSubmittedSignature = "";
  const dynamicSelectionRanges = new Map();
  let mutationVersion = 0;
  let lastMutationAt = 0;
  let mutationObserver = null;
  const STABILITY_QUIET_MS = 350;
  const STABILITY_MAX_WAIT_MS = 1800;
  const BLOCK_TAGS = new Set([
    "ARTICLE", "BLOCKQUOTE", "DD", "DIV", "DT", "H1", "H2", "H3", "H4", "H5", "H6",
    "LI", "P", "PRE", "SECTION", "TD", "TH",
  ]);
  const EXCLUDED_SELECTOR = "script, style, template, nav, aside, footer, form, textarea, input, button, [aria-hidden=\"true\"], [data-lauudit-ignore]";
  const CANDIDATE_SELECTOR = [
    "main", "article", "[role=\"main\"]", "[role=\"article\"]", "[role=\"region\"]",
    "[aria-live]", "[data-testid]", "[id]",
  ].join(",");
  const POSITIVE_HINTS = /(answer|response|result|content|message|conversation|chat|output|completion|prose)/;
  const NEGATIVE_HINTS = /(source|sources|steps|navigation|sidebar|menu|toolbar|header|footer|citation-list|reference-list)/;

  function visible(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE) return false;
    try {
      const style = window.getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
    } catch (_error) {
      return false;
    }
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
    if (!root?.querySelectorAll) return [];
    const elements = [root, ...Array.from(root.querySelectorAll("*"))];
    const blocks = elements.filter((element) => {
      if (excluded(element) || !visible(element) || !nodeText(element)) return false;
      if (element === root) return !hasBlockDescendant(element);
      return BLOCK_TAGS.has(element.tagName) && !hasBlockDescendant(element);
    });
    return blocks.length ? blocks : [root];
  }

  function startMutationObserver() {
    if (mutationObserver || typeof MutationObserver !== "function" || !document.body) return;
    mutationObserver = new MutationObserver(() => {
      mutationVersion += 1;
      lastMutationAt = Date.now();
    });
    mutationObserver.observe(document.body, {childList: true, subtree: true, characterData: true});
  }

  function rootDescription(element) {
    if (!element) return "none";
    const className = typeof element.className === "string" ? element.className : "";
    const label = element.getAttribute("aria-label") || element.id || className || "";
    return `${element.tagName.toLowerCase()}${label ? `[${String(label).trim().slice(0, 120)}]` : ""}`;
  }

  function elementLabel(element) {
    if (!element) return "";
    const className = typeof element.className === "string" ? element.className : "";
    return [
      element.id,
      className,
      element.getAttribute("aria-label"),
      element.getAttribute("role"),
      element.getAttribute("data-testid"),
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function measureCandidate(element) {
    const text = nodeText(element);
    const blocks = contentBlocks(element);
    const anchors = Array.from(element.querySelectorAll("a[href]")).filter((anchor) => visible(anchor) && !excluded(anchor));
    const headings = Array.from(element.querySelectorAll("h1, h2, h3, h4, h5, h6"));
    const paragraphs = Array.from(element.querySelectorAll("p, li, blockquote, pre"));
    const controls = Array.from(element.querySelectorAll("button, input, textarea, select")).length;
    const label = elementLabel(element);
    const positiveHints = (label.match(POSITIVE_HINTS) || []).length;
    const negativeHints = (label.match(NEGATIVE_HINTS) || []).length;
    const linkTextLength = anchors.reduce((total, anchor) => total + nodeText(anchor).length, 0);
    const linkDensity = text.length ? linkTextLength / text.length : 0;
    const role = element.getAttribute("role") || "";
    const semanticBoost = role === "main" || role === "article" || /^(MAIN|ARTICLE)$/.test(element.tagName) ? 1 : 0;
    return {
      text_length: text.length,
      block_count: blocks.length,
      heading_count: headings.length,
      paragraph_count: paragraphs.length,
      link_count: anchors.length,
      link_density: Number(linkDensity.toFixed(3)),
      control_count: controls,
      positive_hints: positiveHints,
      negative_hints: negativeHints,
      semantic_boost: semanticBoost,
      label: label.slice(0, 200),
    };
  }

  function candidateScore(element, metrics) {
    if (!element || excluded(element) || !visible(element) || metrics.text_length < 40) return -Infinity;
    const sizeScore = Math.min(metrics.text_length, 16000) / 40;
    const structureScore = Math.min(metrics.block_count, 40) * 12
      + Math.min(metrics.heading_count, 8) * 18
      + Math.min(metrics.paragraph_count, 40) * 3;
    const semanticScore = metrics.semantic_boost * 140 + metrics.positive_hints * 90;
    const noisePenalty = metrics.negative_hints * 180
      + Math.max(0, metrics.link_density - 0.2) * 220
      + Math.max(0, metrics.control_count - 2) * 15;
    const bodyPenalty = element === document.body ? 650 : 0;
    return Number((sizeScore + structureScore + semanticScore - noisePenalty - bodyPenalty).toFixed(3));
  }

  function candidateReason(metrics, element) {
    const reasons = [];
    if (metrics.semantic_boost) reasons.push("semantic-main-region");
    if (metrics.positive_hints) reasons.push("answer-like-label");
    if (metrics.block_count >= 2) reasons.push("structured-text");
    if (metrics.heading_count) reasons.push("contains-headings");
    if (metrics.negative_hints) reasons.push("contains-exclusion-hints");
    if (element === document.body) reasons.push("document-body-fallback");
    return reasons;
  }

  function candidateElements() {
    const candidates = [document.body, ...Array.from(document.querySelectorAll(CANDIDATE_SELECTOR))];
    const structural = Array.from(document.querySelectorAll("article, main, section, div, li, blockquote, pre"))
      .filter((element) => element.childElementCount > 0 || nodeText(element).length >= 160)
      .slice(0, 180);
    candidates.push(...structural);
    return candidates.filter((element, index, values) => element && values.indexOf(element) === index);
  }

  function chooseResponseRoot() {
    const ranked = candidateElements()
      .filter((element) => !excluded(element) && visible(element))
      .map((element) => {
        const metrics = measureCandidate(element);
        return {element, metrics, score: candidateScore(element, metrics)};
      })
      .filter((candidate) => Number.isFinite(candidate.score))
      .sort((first, second) => second.score - first.score);
    const fallback = document.body;
    if (!ranked.length) {
      return {root: fallback, ranked: [], confidence: 0.2, warnings: ["NO_CREDIBLE_RESPONSE_REGION"]};
    }
    const best = ranked[0];
    const second = ranked[1];
    const gap = second ? best.score - second.score : 240;
    let confidence = Math.max(0.2, Math.min(0.99, 0.5 + gap / 500));
    if (best.element === document.body) confidence *= 0.65;
    if (best.metrics.negative_hints) confidence *= 0.75;
    const warnings = [];
    if (best.element === document.body) warnings.push("BODY_FALLBACK_SELECTED");
    if (second && gap < 75) warnings.push("MULTIPLE_CANDIDATE_REGIONS");
    if (best.metrics.negative_hints) warnings.push("SELECTED_REGION_HAS_EXCLUSION_HINTS");
    return {root: best.element, ranked, confidence: Number(confidence.toFixed(3)), warnings};
  }

  function excludedRegions() {
    return Array.from(document.querySelectorAll(EXCLUDED_SELECTOR))
      .filter((element) => visible(element))
      .slice(0, 40)
      .map((element) => ({region: rootDescription(element), text_length: nodeText(element).length, reason: "excluded-selector"}));
  }

  function isPageStable() {
    return !lastMutationAt || Date.now() - lastMutationAt >= STABILITY_QUIET_MS;
  }

  function collectPageCapture({waitedMs = 0} = {}) {
    startMutationObserver();
    const selection = chooseResponseRoot();
    const root = selection.root;
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
          const mapped = localStart >= 0 && text.slice(localStart, localStart + linkText.length) === linkText;
          const link = {
            text: linkText,
            href: anchor.href,
            context: text,
            block_id: `block-${blockIndex + 1}`,
            mapping_status: mapped ? "EXACT" : "UNMAPPED",
          };
          if (mapped) {
            link.start = start + localStart;
            link.end = start + localStart + linkText.length;
            linkCursor = Math.max(linkCursor, localStart + linkText.length);
          }
          links.push(link);
        });
      return {id: `block-${blockIndex + 1}`, tag: element.tagName.toLowerCase(), text, start, end};
    });
    const candidateRegions = selection.ranked.slice(0, 12).map((candidate, index) => ({
      candidate_id: `candidate-${index + 1}`,
      region: rootDescription(candidate.element),
      selected: candidate.element === root,
      score: candidate.score,
      reasons: candidateReason(candidate.metrics, candidate.element),
      metrics: candidate.metrics,
    }));
    const unmappedLinkCount = links.filter((link) => link.mapping_status !== "EXACT").length;
    const stable = isPageStable();
    const warnings = [...selection.warnings];
    if (!stable) warnings.push("CONTENT_RECENTLY_CHANGED");
    if (unmappedLinkCount) warnings.push("LINK_OFFSETS_UNMAPPED");
    if (selection.confidence < 0.6) warnings.push("LOW_CAPTURE_CONFIDENCE");
    return {
      response_text: responseText,
      links,
      content_blocks: structuredBlocks,
      candidate_regions: candidateRegions,
      excluded_regions: excludedRegions(),
      capture_diagnostics: {
        method: "semantic-dom",
        root: rootDescription(root),
        fallback_to_body: root === document.body,
        confidence: selection.confidence,
        stable,
        waited_ms: waitedMs,
        mutation_version: mutationVersion,
        candidate_count: selection.ranked.length,
        selected_score: selection.ranked[0]?.score ?? null,
        block_count: structuredBlocks.length,
        text_length: responseText.length,
        link_count: links.length,
        unmapped_link_count: unmappedLinkCount,
        omitted_content: root !== document.body,
        warnings,
      },
    };
  }

  function collectResponse(options = {}) {
    const capture = collectPageCapture(options);
    return {...capture, page_url: location.href, user_query: null, jurisdiction: "Singapore", as_of_date: new Date().toISOString().slice(0, 10)};
  }

  function collectStableResponse() {
    startMutationObserver();
    const startedAt = Date.now();
    return new Promise((resolve) => {
      const check = () => {
        const waitedMs = Date.now() - startedAt;
        if (isPageStable() || waitedMs >= STABILITY_MAX_WAIT_MS) {
          resolve(collectResponse({waitedMs}));
          return;
        }
        setTimeout(check, STABILITY_QUIET_MS);
      };
      check();
    });
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
    if (message.type === "COLLECT_RESPONSE_STABLE") {
      collectStableResponse().then(sendResponse);
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
  startMutationObserver();
})();

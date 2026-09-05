(() => {
  function visible(element) {
    const style = window.getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
  }

  function collectResponse() {
    const responseText = document.body ? document.body.innerText : "";
    const links = Array.from(document.querySelectorAll("a[href]"))
      .filter(visible)
      .map((anchor) => ({
        text: (anchor.innerText || anchor.textContent || "").trim(),
        href: anchor.href,
        context: (anchor.closest("p, li, article, main, section") || anchor.parentElement || document.body).innerText.trim()
      }))
      .filter((link) => link.text || link.href);
    return {response_text: responseText, links, page_url: location.href, user_query: null, jurisdiction: "Singapore", as_of_date: new Date().toISOString().slice(0, 10)};
  }

  function highlight(results) {
    const byText = new Map(results.map((item) => [item.raw_text, item.status]));
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      if (!node.nodeValue.trim() || node.parentElement.closest("script, style, textarea, input, button")) return;
      let current = node.nodeValue;
      const fragment = document.createDocumentFragment();
      let changed = false;
      byText.forEach((status, raw) => {
        const offset = current.indexOf(raw);
        if (offset < 0) return;
        if (offset) fragment.appendChild(document.createTextNode(current.slice(0, offset)));
        const mark = document.createElement("mark");
        mark.className = status === "VERIFIED_EXISTS" ? "lca-verified" : (status.includes("UNCERTAIN") || status.includes("AMBIGUOUS") ? "lca-uncertain" : "lca-error");
        mark.textContent = raw;
        mark.title = status;
        fragment.appendChild(mark);
        current = current.slice(offset + raw.length);
        changed = true;
      });
      if (changed) {
        if (current) fragment.appendChild(document.createTextNode(current));
        node.parentNode.replaceChild(fragment, node);
      }
    });
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === "COLLECT_RESPONSE") {
      sendResponse(collectResponse());
      return true;
    }
    if (message.type === "HIGHLIGHT_RESULTS") {
      highlight(message.results || []);
      sendResponse({ok: true});
      return true;
    }
  });
})();


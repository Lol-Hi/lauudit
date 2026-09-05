# Architecture

The extension reads visible DOM content on a user action. It builds a page-agnostic semantic capture by ranking visible candidate regions, excluding common page chrome, preserving block/link offsets, and reporting capture confidence and stability. The service worker waits for a quiet DOM before forwarding the payload to the local FastAPI service. The service uses deterministic extraction, SQLite exact/fuzzy lookup, link metadata comparison, and paragraph token-overlap retrieval with conservative thresholds. The browser then displays the JSON result and highlights extracted citation text.

The reader is deliberately not tied to a LawNet-specific selector. It uses semantic HTML, ARIA roles, layout visibility, text structure, link density, nested exclusion hints, open shadow-root traversal, and mutation stability. Candidate selection is explainable through `candidate_regions` and `capture_diagnostics`; low-confidence or incomplete captures are reported rather than silently treated as complete.

The local corpus is deliberately a declared boundary. A corpus miss is `NOT_FOUND_IN_VERIFIED_CORPUS`, not a claim that no such case exists.

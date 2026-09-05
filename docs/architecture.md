# Architecture

The extension reads visible DOM content on a user action. The service worker forwards the payload to the local FastAPI service. The service uses deterministic extraction, SQLite exact/fuzzy lookup, link metadata comparison, and paragraph token-overlap retrieval with conservative thresholds. The browser then displays the JSON result and highlights extracted citation text.

The local corpus is deliberately a declared boundary. A corpus miss is `NOT_FOUND_IN_VERIFIED_CORPUS`, not a claim that no such case exists.


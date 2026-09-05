# Corpus metadata schema

`data/corpus/cases.jsonl` is newline-delimited JSON. Required fields are:

`case_id`, `canonical_name`, `aliases`, `neutral_citation` or `reported_citations`, `court`, `court_code`, `decision_date`, `source_url`, `document_path`, and `source_type`.

Documents may be permitted plain-text files or local PDFs. Blank-line-separated
blocks are paragraphs. A leading number such as `[42]` preserves the judgment
paragraph number for evidence display. PDF paragraphs also retain their
one-based page number.

For PDF records, `text_source` may be `native_pdf` or `ocr`; it defaults to
`native_pdf` when omitted. Plain-text records default to `plain_text`. `ocr`
means that the maintainer has identified the extracted text as OCR-derived; the
indexer does not perform OCR itself. A PDF with no extractable text is rejected
until an approved text layer or OCR-processed copy is prepared.

Audit evidence includes `paragraph`, optional `page`, `text`, `score`, and
`text_source`. Page is null for plain-text evidence.

Audit citation results also include `source_status`, `source_url_normalized`, and
the optional `source_discovery` marker. These are offline URL provenance and
discovery signals. `OFFICIAL_ELITIGATION_SOURCE` and
`OFFICIAL_JUDICIARY_SOURCE` identify an official domain;
`TRUSTED_PUBLISHER_SOURCE` identifies a Singapore Law Watch publisher URL.
None of these statuses confirms that the page is live or that it contains the
cited case. `KNOWN_CORPUS_SOURCE` means the normalized URL matches a local
corpus record. `OFFICIAL_ELITIGATION_SEARCH` means the backend found the
direct URL through the official eLitigation judgments index; the separate
`live_verification` result contains the metadata comparison. Search-page
statuses are discovery signals only.

Citation extraction also exposes `parallel_citations` for grouped parallel references, `context_type` (`body` or `footnote`), and an optional `footnote_number`. `provided_citation` remains the primary citation for backward compatibility. Link matching may return `LINK_SPLIT_OR_AMBIGUOUS` when adjacent citation fragments point to different URLs.

## Page-reading capture

The extension sends the backend a structured capture in addition to the
backward-compatible `response_text` and `links` fields:

- `content_blocks` contains the selected visible blocks and their exact `start`
  and `end` offsets in `response_text`;
- each link may include `block_id`, `mapping_status`, `start`, and `end`;
- `candidate_regions` records response-region candidates, scores, reasons, and
  measurable features used for selection;
- `excluded_regions` records visible regions removed by generic exclusion rules;
- `capture_diagnostics` records the capture method, confidence, mutation
  stability, selected root, link-mapping failures, iframe/shadow-root limits,
  and warnings.

The backend returns `capture_diagnostics` unchanged with the audit response so
the extension can show when a page was captured with low confidence or while it
was still changing. Positional link metadata is preferred for citation matching;
older clients without offsets continue to use the text/context fallback.

## Corpus provenance

Every successful index build records one row in `corpus_snapshots` and one row per case in `case_provenance`:

- `snapshot_id` is derived from the metadata hash, document hashes, source URLs, and source types;
- `cases_sha256` identifies the exact metadata file used;
- `document_sha256` and `document_size_bytes` identify the exact local text file indexed;
- `source_url` records where the maintainer obtained or verified the judgment;
- `source_verified` records the maintainer's explicit verification decision and is not inferred from the URL's domain;
- `retrieved_at` records an optional timezone-aware ISO-8601 retrieval timestamp;
- `completeness` and `notes` state the declared scope of the corpus.

The audit API exposes `corpus_snapshot`, `corpus_completeness`, and `corpus_notes`. A snapshot is provenance for local indexed content; it is not a claim that the source URL is currently reachable or that the corpus is complete.

Successful builds also write `data/corpus/build_report.json`. It records the snapshot ID, metadata hash, record/document counts, completeness, notes, and `offline_build: true`. The report contains no judgment text.

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

Audit citation results also include `source_status` and `source_url_normalized`. These are offline URL provenance signals. `OFFICIAL_ELITIGATION_SOURCE` and `OFFICIAL_JUDICIARY_SOURCE` identify an official domain; `TRUSTED_PUBLISHER_SOURCE` identifies a Singapore Law Watch publisher URL. None of these statuses confirms that the page is live or that it contains the cited case. `KNOWN_CORPUS_SOURCE` means the normalized URL matches a local corpus record. Search-page statuses are discovery signals only.

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

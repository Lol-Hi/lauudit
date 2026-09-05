# Corpus metadata schema

`data/corpus/cases.jsonl` is newline-delimited JSON. Required fields are:

`case_id`, `canonical_name`, `aliases`, `neutral_citation` or `reported_citations`, `court`, `court_code`, `decision_date`, `source_url`, `document_path`, and `source_type`.

Documents are plain text. Blank-line-separated blocks are paragraphs. A leading number such as `[42]` preserves the judgment paragraph number for evidence display.

Audit citation results also include `source_status` and `source_url_normalized`. These are offline URL provenance signals. `OFFICIAL_ELITIGATION_SOURCE` and `OFFICIAL_JUDICIARY_SOURCE` identify an official domain; `TRUSTED_PUBLISHER_SOURCE` identifies a Singapore Law Watch publisher URL. None of these statuses confirms that the page is live or that it contains the cited case. `KNOWN_CORPUS_SOURCE` means the normalized URL matches a local corpus record. Search-page statuses are discovery signals only.

## Corpus provenance

Every successful index build records one row in `corpus_snapshots` and one row per case in `case_provenance`:

- `snapshot_id` is derived from the metadata hash, document hashes, source URLs, and source types;
- `cases_sha256` identifies the exact metadata file used;
- `document_sha256` and `document_size_bytes` identify the exact local text file indexed;
- `source_url` records where the maintainer obtained or verified the judgment;
- `completeness` and `notes` state the declared scope of the corpus.

The audit API exposes `corpus_snapshot`, `corpus_completeness`, and `corpus_notes`. A snapshot is provenance for local indexed content; it is not a claim that the source URL is currently reachable or that the corpus is complete.

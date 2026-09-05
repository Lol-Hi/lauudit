# Corpus metadata schema

`data/corpus/cases.jsonl` is newline-delimited JSON. Required fields are:

`case_id`, `canonical_name`, `aliases`, `neutral_citation` or `reported_citations`, `court`, `court_code`, `decision_date`, `source_url`, `document_path`, and `source_type`.

Documents are plain text. Blank-line-separated blocks are paragraphs. A leading number such as `[42]` preserves the judgment paragraph number for evidence display.

Audit citation results also include `source_status` and `source_url_normalized`. These are offline URL provenance signals. `OFFICIAL_ELITIGATION_SOURCE` and `OFFICIAL_JUDICIARY_SOURCE` identify an official domain; they do not confirm that the page is live or that it contains the cited case. `KNOWN_CORPUS_SOURCE` means the normalized URL matches a local corpus record.

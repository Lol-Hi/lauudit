# Corpus metadata schema

`data/corpus/cases.jsonl` is newline-delimited JSON. Required fields are:

`case_id`, `canonical_name`, `aliases`, `neutral_citation` or `reported_citations`, `court`, `court_code`, `decision_date`, `source_url`, `document_path`, and `source_type`.

Documents are plain text. Blank-line-separated blocks are paragraphs. A leading number such as `[42]` preserves the judgment paragraph number for evidence display.


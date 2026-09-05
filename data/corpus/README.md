# Local corpus

Place permitted plain-text Singapore judgments in `documents/` and add matching metadata records to `cases.jsonl`. The two checked-in records are synthetic demo documents and are not legal authorities. Do not add documents unless the team has permission to use and index them.

For a private/local corpus, use `private_documents/`; for optional locally retained source PDFs, use `source_pdfs/`. Both directories are Git-ignored. These files are prepared once by the corpus maintainer and are never downloaded by the Chrome extension or by the audit API. The index stores extracted paragraph text and provenance hashes in SQLite, not the original PDFs.

The Singapore Law Watch [Judgments page](https://www.singaporelawwatch.sg/Judgments) can be used for manual discovery. Record the direct judgment/PDF URL in `source_url`, but obtain the file and confirm permission separately before indexing it. A search-page URL is discovery evidence, not proof that it is the source for a specific case.

After updating the corpus, run `python scripts/build_index.py`. The output includes a deterministic snapshot ID and the SHA-256 hash of `cases.jsonl`. The active audit response reports that snapshot ID and whether the corpus is `partial`, `comprehensive`, or `unknown`.

The indexer treats blank-line-separated blocks as paragraphs. A block beginning with `[42]` is indexed with paragraph number `42`; otherwise paragraph numbers are assigned in document order.

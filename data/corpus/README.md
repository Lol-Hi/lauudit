# Local corpus

Place permitted plain-text Singapore judgments in `documents/` and add matching metadata records to `cases.jsonl`. The two checked-in records are synthetic demo documents and are not legal authorities. Do not add documents unless the team has permission to use and index them.

The indexer treats blank-line-separated blocks as paragraphs. A block beginning with `[42]` is indexed with paragraph number `42`; otherwise paragraph numbers are assigned in document order.


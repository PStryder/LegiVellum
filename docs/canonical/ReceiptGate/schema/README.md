# ReceiptGate schema — moved

The executable schema lives in the ReceiptGate repository, at
`ReceiptGate/schema/`. It is applied on startup by `receiptgate.db.apply_schema`
and is the only copy that runs.

Copies of `001`–`004` used to sit in this directory. They are gone because they
were a second source of truth that had quietly stopped being true:

- all four had drifted from the originals
- `005_receipts_v1.sql` and `006_obligations.sql` were never copied here at all,
  so the tables holding the authoritative answer to "who owes what" —
  `obligations`, `custody_state`, and the partial unique index
  `idx_custody_one_live_grant` that enforces at most one live custody grant per
  obligation — were absent from the copy a reader was told to treat as canonical

The one duplicated artifact in this tree that has a test asserting the two
copies agree, `receipt.schema.v1.json`, is byte-identical to the packaged one
(`LegiVellum/tests/test_protocol_package.py`). The four that had no such test
all drifted. That is the whole argument for not keeping a second copy of
something executable.

For the contract these tables implement, see `transitions.v1.json` and
`authority.v1.json` in `legivellum/schemas/`, which are loaded by the code that
evaluates transitions rather than transcribed into prose.

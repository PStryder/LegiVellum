"""LegiVellum carries no schema for tables it does not own.

LegiVellum is the protocol package and the Problemata control plane. Storage
belongs to the gates, each of which owns its own database: ReceiptGate has
`receipts`, `obligations` and `custody_state`; AsyncGate has `tasks` and
`leases`; DeleGate has `plans`.

`schema/` used to contain `receipts.sql`, `tasks.sql`, `plans.sql` and an
`init.sql` that built all of them into one database -- left over from when
LegiVellum was a single service. Nothing ran them. The only loader was a test
fixture no test requested, and one of the four files it listed had not existed
for some time.

The cost of keeping them was not disk. A reader looking for the receipts schema
found a plausible, complete, *stale* one: no `obligation_id`, no custody tables,
and an inbox index built on `phase = 'accepted'` -- the model custody replaced.
The live schema is in ReceiptGate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "schema"

# Tables owned by a gate, not by LegiVellum. Naming them individually rather
# than pattern-matching keeps the failure message specific about which
# component's storage has been copied in.
GATE_TABLES = {
    "receipts": "ReceiptGate",
    "receipts_v1": "ReceiptGate",
    "obligations": "ReceiptGate",
    "custody_state": "ReceiptGate",
    "tasks": "AsyncGate",
    "leases": "AsyncGate",
    "plans": "DeleGate",
    "workers": "AsyncGate",
}


def _sql_files() -> list[Path]:
    return sorted(REPO.glob("**/*.sql"))


def _created_tables(text: str) -> set[str]:
    return {
        name.lower()
        for name in re.findall(
            r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+([A-Za-z_][A-Za-z0-9_]*)",
            text,
            re.IGNORECASE,
        )
    }


@pytest.mark.parametrize("path", _sql_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_no_sql_file_creates_another_components_table(path):
    # No exemption for docs/canonical. Copies of ReceiptGate's DDL lived there
    # too, drifted, and were removed in favour of a pointer; a normative tree is
    # the worst place to keep a stale duplicate, not an acceptable one.
    trespassing = _created_tables(path.read_text(encoding="utf-8")) & set(GATE_TABLES)
    assert not trespassing, (
        f"{path.relative_to(REPO)} creates "
        + ", ".join(f"{t} (owned by {GATE_TABLES[t]})" for t in sorted(trespassing))
        + ". A second definition of a table another service owns will drift from "
        "the one that actually runs, and it is the copy a reader finds first."
    )


def test_schema_holds_only_the_control_plane():
    """The one thing LegiVellum does own storage for."""
    files = {p.name for p in SCHEMA.rglob("*.sql")}
    assert files == {"001_problemata_registry.sql"}, sorted(files)


def test_no_fixture_loads_ddl_from_disk():
    """The loader is gone with the files.

    It listed `schema/workers.sql`, which did not exist, and skipped it via an
    `os.path.exists` guard -- so a missing schema file was indistinguishable
    from a present one, and no test noticed either way.
    """
    conftest = (REPO / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert ".sql" not in conftest, (
        "conftest reads DDL from disk again; LegiVellum runs no database and "
        "its tests must not build another component's tables"
    )

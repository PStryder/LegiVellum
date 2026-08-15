#!/usr/bin/env python3
"""Phase 0 exit condition: canonical validation works inside the built image.

Run *inside* a built ReceiptGate or AsyncGate container, against whatever that
image actually contains. No repository checkout, no bind mount, no sys.path
manipulation, no parent-directory walking -- if this passes, the image can
validate receipts; if it fails, the image must not ship.

It exists because the defect it guards against was invisible by construction.
`legivellum` was resolved by walking parent directories for a source tree that
exists in a checkout and not in an image. In containers the walk found nothing,
`except ImportError` set the model to None, and every emitter degraded to
posting unvalidated dictionaries. Canonical validation was off in production
across the stack while the test suites -- run in checkouts, where the walk
succeeds -- were green.

So this probe is deliberately hostile to source-tree tricks:

  1. import legivellum.validation
  2. assert the schema resolves to a path inside the installed package
  3. validate a known-good canonical receipt      -> must pass
  4. validate a known-bad canonical receipt       -> must be rejected
  5. assert the validator fails closed when it cannot find its rules

Usage (from the stack root):

    docker build -f ReceiptGate/Dockerfile -t receiptgate:probe .
    docker run --rm -v "$PWD/LegiVellum/problemata_demo:/probe:ro" \
        receiptgate:probe python /probe/container_validation_probe.py

Exits non-zero on any failure.
"""

from __future__ import annotations

import sys
import traceback

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}" + (f" -- {detail}" if detail else ""))
        FAILURES.append(name)


# A canonical `accepted` receipt, inlined rather than read from the repository.
# The whole point is to depend on nothing outside the image.
GOOD_RECEIPT = {
    "schema_version": "1.0",
    "tenant_id": "default",
    "receipt_id": "01J0PROBE0000000000000000",
    "task_id": "T-probe-1",
    "obligation_id": "01J0OBLIG0PROBE0000000000A",
    "parent_task_id": "NA",
    "caused_by_receipt_id": "NA",
    "dedupe_key": "probe:accepted",
    "attempt": 0,
    "from_principal": "sys:legivellum",
    "for_principal": "agent:probe",
    "source_system": "probe",
    "recipient_ai": "agent:probe",
    "trust_domain": "default",
    "phase": "accepted",
    "status": "NA",
    "realtime": True,
    "task_type": "probe.check",
    "task_summary": "Container validation probe",
    "task_body": "Assert the image can validate a canonical receipt.",
    "inputs": {},
    "expected_outcome_kind": "response_text",
    "expected_artifact_mime": "NA",
    "outcome_kind": "NA",
    "outcome_text": "NA",
    "artifact_location": "NA",
    "artifact_pointer": "NA",
    "artifact_checksum": "NA",
    "artifact_size_bytes": 0,
    "artifact_mime": "NA",
    "escalation_class": "NA",
    "escalation_reason": "NA",
    "escalation_to": "NA",
    "retry_requested": False,
    "body": {},
    "created_at": "2026-08-15T00:00:00+00:00",
    "stored_at": None,
    "started_at": "2026-08-15T00:00:00+00:00",
    "completed_at": None,
    "read_at": None,
    "archived_at": None,
    "metadata": {},
}


def main() -> int:
    print("Phase 0 container validation probe")
    print(f"  python   : {sys.version.split()[0]}")

    # 1. The protocol package must import at all.
    try:
        import legivellum
        from legivellum import validation
    except Exception:
        traceback.print_exc()
        print("\nFAILED: legivellum is not importable inside this image.")
        print("The image must install the canonical protocol package.")
        return 1

    print(f"  package  : legivellum {legivellum.__version__}")

    # 2. The schema must come from the installed package, not a checkout.
    try:
        path = validation.schema_path()
    except Exception as exc:
        print(f"  FAIL  schema resolution raised: {exc}")
        return 1

    print(f"  schema   : {path}")
    check(
        "schema resolves inside the installed package",
        "site-packages" in str(path) or "dist-packages" in str(path),
        f"resolved to {path}, which looks like a source checkout rather than the "
        f"installed package; this probe would then be testing the repository, "
        f"not the image",
    )

    # 3. A known-good canonical receipt validates.
    errors = validation.validate_json_schema(GOOD_RECEIPT)
    check(
        "known-good canonical receipt validates",
        errors == [],
        "; ".join(e.message for e in errors),
    )

    # 4. A known-bad receipt is rejected. An `accepted` receipt carries an open
    #    obligation, so the schema forbids it declaring a real outcome.
    bad = dict(GOOD_RECEIPT)
    bad["outcome_kind"] = "response_text"
    check(
        "known-bad canonical receipt is rejected",
        validation.validate_json_schema(bad) != [],
        "the validator accepted a receipt the canonical rules forbid",
    )

    # 4b. obligation_id is required as of schema v1.1. Without it a terminal
    #     receipt can only be matched to an obligation by task_id, which is how
    #     one completion came to discharge several independent obligations.
    missing_obligation = {k: v for k, v in GOOD_RECEIPT.items() if k != "obligation_id"}
    check(
        "receipt without obligation_id is rejected",
        validation.validate_json_schema(missing_obligation) != [],
        "obligation_id is not required; obligations have no identity",
    )

    # 5. additionalProperties: false must hold. This is what rejects a
    #    top-level `receipt_type`, the field AsyncGate's older model carried.
    extra = dict(GOOD_RECEIPT)
    extra["receipt_type"] = "task.assigned"
    check(
        "unknown top-level field is rejected",
        validation.validate_json_schema(extra) != [],
        "additionalProperties: false is not being enforced",
    )

    # 6. Fail closed. A validator that cannot find its rules must raise rather
    #    than report success, which is the exact bug that hid all of the above.
    import os

    os.environ[validation.SCHEMA_DIR_ENV] = "/nonexistent/schema/dir"
    try:
        validation.schema_path()
        check("missing schema fails closed", False, "schema_path() returned instead of raising")
    except RuntimeError:
        check("missing schema fails closed", True)
    except Exception as exc:
        check("missing schema fails closed", False, f"raised {type(exc).__name__}, expected RuntimeError")
    finally:
        del os.environ[validation.SCHEMA_DIR_ENV]

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All container validation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

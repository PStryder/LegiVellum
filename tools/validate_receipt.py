#!/usr/bin/env python3
"""Validate LegiVellum receipts against the JSON Schema.

Usage:
  python tools/validate_receipt.py path/to/receipt.json [--schema spec/receipt.schema.v1.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_routing_invariant(receipt: dict) -> list[str]:
    """Validate application-level invariants not expressible in JSON Schema."""
    errors = []
    
    # Routing invariant: phase=escalate requires recipient_ai == escalation_to
    if receipt.get("phase") == "escalate":
        recipient_ai = receipt.get("recipient_ai")
        escalation_to = receipt.get("escalation_to")
        if recipient_ai != escalation_to:
            errors.append(
                f"Routing invariant violation: recipient_ai='{recipient_ai}' "
                f"must equal escalation_to='{escalation_to}' when phase='escalate'"
            )
    
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt", type=Path, help="Path to receipt JSON file")
    ap.add_argument("--schema", type=Path, default=Path("spec/receipt.schema.v1.json"), help="Path to receipt schema JSON")
    args = ap.parse_args()

    schema = load_json(args.schema)
    receipt = load_json(args.receipt)

    # Schema validation
    v = Draft202012Validator(schema)
    schema_errors = sorted(v.iter_errors(receipt), key=lambda e: e.path)
    
    # Application-level validation
    app_errors = validate_routing_invariant(receipt)

    all_errors = []
    
    if schema_errors:
        for err in schema_errors:
            path = ".".join([str(p) for p in err.path]) or "<root>"
            all_errors.append(f"Schema: {path}: {err.message}")
    
    if app_errors:
        for err in app_errors:
            all_errors.append(f"Invariant: {err}")

    if not all_errors:
        print("OK: receipt is valid")
        return 0

    print(f"INVALID: {len(all_errors)} error(s)")
    for err in all_errors:
        print(f"- {err}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

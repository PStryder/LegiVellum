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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt", type=Path, help="Path to receipt JSON file")
    ap.add_argument("--schema", type=Path, default=Path("spec/receipt.schema.v1.json"), help="Path to receipt schema JSON")
    args = ap.parse_args()

    schema = load_json(args.schema)
    receipt = load_json(args.receipt)

    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(receipt), key=lambda e: e.path)

    if not errors:
        print("OK: receipt is valid")
        return 0

    print(f"INVALID: {len(errors)} error(s)")
    for err in errors:
        path = ".".join([str(p) for p in err.path]) or "<root>"
        print(f"- {path}: {err.message}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

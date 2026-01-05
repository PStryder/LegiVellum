#!/usr/bin/env python3
"""Validate all example receipts in examples/receipts/ directory.

Usage:
  python tools/validate_all_examples.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import subprocess


def main() -> int:
    """Run validator on all example receipts."""
    examples_dir = Path("examples/receipts")
    
    if not examples_dir.exists():
        print(f"ERROR: Examples directory not found: {examples_dir}")
        return 1
    
    # Find all JSON files in examples directory
    receipt_files = sorted(examples_dir.glob("*.json"))
    
    if not receipt_files:
        print(f"WARNING: No .json files found in {examples_dir}")
        return 0
    
    print(f"Validating {len(receipt_files)} example receipt(s)...\n")
    
    failed = []
    passed = []
    
    for receipt_file in receipt_files:
        print(f"Validating {receipt_file.name}...", end=" ")
        
        try:
            result = subprocess.run(
                ["python", "tools/validate_receipt.py", str(receipt_file)],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                print("[PASS]")
                passed.append(receipt_file.name)
            else:
                print("[FAIL]")
                print(f"  {result.stdout}")
                if result.stderr:
                    print(f"  {result.stderr}")
                failed.append(receipt_file.name)
        except Exception as e:
            print(f"[ERROR]: {e}")
            failed.append(receipt_file.name)
    
    print(f"\n{'='*60}")
    print(f"Results: {len(passed)} passed, {len(failed)} failed")
    
    if failed:
        print(f"\nFailed files:")
        for name in failed:
            print(f"  - {name}")
        return 1
    
    print("\n[SUCCESS] All examples valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

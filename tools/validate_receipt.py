#!/usr/bin/env python3
"""
LegiVellum Receipt Validator

Validates JSON receipts against the LegiVellum Receipt v1 schema.
Usage:
    python validate_receipt.py <receipt.json>
    python validate_receipt.py --schema <schema.json> <receipt.json>
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List

try:
    import jsonschema
    from jsonschema import validate, ValidationError
except ImportError:
    print("ERROR: jsonschema library not found.")
    print("Install with: pip install jsonschema")
    sys.exit(1)


DEFAULT_SCHEMA_PATH = Path(__file__).parent.parent / "spec" / "receipt.schema.v1.json"


def load_json(filepath: Path) -> Dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {filepath}: {e}")
        sys.exit(1)


def validate_receipt(receipt: Dict[str, Any], schema: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate receipt against schema.
    
    Returns:
        (is_valid, errors) tuple
    """
    errors = []
    
    try:
        validate(instance=receipt, schema=schema)
        return True, []
    except ValidationError as e:
        errors.append(f"Validation error: {e.message}")
        if e.path:
            errors.append(f"  at: {'.'.join(str(p) for p in e.path)}")
        return False, errors


def main():
    """Main validator entry point."""
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python validate_receipt.py [--schema <schema.json>] <receipt.json>")
        sys.exit(1)
    
    schema_path = DEFAULT_SCHEMA_PATH
    receipt_path = None
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--schema":
            if i + 1 >= len(sys.argv):
                print("ERROR: --schema requires a path argument")
                sys.exit(1)
            schema_path = Path(sys.argv[i + 1])
            i += 2
        else:
            receipt_path = Path(sys.argv[i])
            i += 1
    
    if not receipt_path:
        print("ERROR: No receipt file specified")
        sys.exit(1)
    
    # Load schema
    print(f"Loading schema: {schema_path}")
    schema = load_json(schema_path)
    
    # Load receipt
    print(f"Loading receipt: {receipt_path}")
    receipt = load_json(receipt_path)
    
    # Validate
    print("Validating...")
    is_valid, errors = validate_receipt(receipt, schema)
    
    if is_valid:
        print("✅ Receipt is VALID")
        
        # Print summary
        print(f"\nReceipt Summary:")
        print(f"  receipt_id: {receipt.get('receipt_id')}")
        print(f"  task_id: {receipt.get('task_id')}")
        print(f"  phase: {receipt.get('phase')}")
        print(f"  recipient_ai: {receipt.get('recipient_ai')}")
        if receipt.get('phase') == 'complete':
            print(f"  status: {receipt.get('status')}")
        elif receipt.get('phase') == 'escalate':
            print(f"  escalation_class: {receipt.get('escalation_class')}")
            print(f"  escalation_to: {receipt.get('escalation_to')}")
        
        return 0
    else:
        print("❌ Receipt is INVALID")
        print("\nErrors:")
        for error in errors:
            print(f"  {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

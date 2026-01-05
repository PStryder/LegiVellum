# Invalid Receipt Examples

This directory contains deliberately invalid receipts for testing schema validation.

Each example violates a specific rule from the Receipt Protocol v1 specification.

## Examples

### `complete_null_timestamp.json`
**Violation:** `phase=complete` with `completed_at=null`  
**Rule:** When phase='complete', completed_at MUST be a valid ISO 8601 timestamp  
**Expected Error:** Schema validation error on completed_at type

### `artifact_pointer_na.json`
**Violation:** `outcome_kind=artifact_pointer` with `artifact_pointer="NA"`  
**Rule:** When outcome_kind is 'artifact_pointer' or 'mixed', artifact fields MUST NOT be "NA"  
**Expected Error:** Schema validation errors on artifact_pointer, artifact_location, artifact_mime

### `routing_invariant_violation.json`
**Violation:** `phase=escalate` with `recipient_ai != escalation_to`  
**Rule:** When phase='escalate', recipient_ai MUST equal escalation_to (routing invariant)  
**Expected Error:** Application-level validation error

### `missing_receipt_id.json`
**Violation:** Missing required `receipt_id` field  
**Rule:** receipt_id is a required field in all receipts  
**Expected Error:** Schema validation error for missing required property

## Testing

These examples are intentionally NOT validated by `tools/validate_all_examples.py` (which only validates the top-level examples directory).

To test validation of these invalid examples manually:

```bash
python tools/validate_receipt.py examples/receipts/invalid/complete_null_timestamp.json
python tools/validate_receipt.py examples/receipts/invalid/artifact_pointer_na.json
python tools/validate_receipt.py examples/receipts/invalid/routing_invariant_violation.json
python tools/validate_receipt.py examples/receipts/invalid/missing_receipt_id.json
```

All four MUST fail validation with appropriate error messages.

# LegiVellum Shared Library

Common models, schemas, and utilities for the LegiVellum system.

## Components

- `models.py` - Pydantic models for receipts and API contracts
- `validation.py` - Receipt validation utilities
- `database.py` - PostgreSQL connection utilities
- `auth.py` - Authentication/authorization utilities

## Installation

```bash
pip install -e .
```

## Usage

```python
from legivellum import Receipt, Phase, validate_receipt

# Create a receipt
receipt = Receipt(
    task_id="T-123",
    from_principal="user.pstryder",
    for_principal="agent.kee",
    source_system="asyncgate",
    recipient_ai="kee",
    phase=Phase.ACCEPTED,
    task_type="code.generate",
    task_summary="Generate React component",
)

# Validate receipt data
errors = validate_receipt(receipt.model_dump())
```

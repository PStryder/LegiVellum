"""
LegiVellum Receipt Validation

Additional validation utilities beyond Pydantic model validation.
"""
from typing import Any
from .models import Receipt, ReceiptCreate, Phase


class ValidationError(Exception):
    """Receipt validation error with structured details"""

    def __init__(self, message: str, field: str = None, constraint: str = None):
        self.message = message
        self.field = field
        self.constraint = constraint
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "constraint": self.constraint,
            "message": self.message,
        }


# Field size limits (in bytes)
FIELD_SIZE_LIMITS = {
    "inputs": 64 * 1024,      # 64 KB
    "metadata": 16 * 1024,    # 16 KB
    "task_body": 100 * 1024,  # 100 KB
    "outcome_text": 100 * 1024,  # 100 KB
}


def validate_field_sizes(data: dict[str, Any]) -> list[ValidationError]:
    """Validate field sizes don't exceed limits"""
    errors = []

    for field, limit in FIELD_SIZE_LIMITS.items():
        if field in data:
            value = data[field]
            if isinstance(value, str):
                size = len(value.encode('utf-8'))
            elif isinstance(value, dict):
                import json
                size = len(json.dumps(value).encode('utf-8'))
            else:
                continue

            if size > limit:
                errors.append(ValidationError(
                    message=f"{field} exceeds size limit of {limit} bytes (got {size})",
                    field=field,
                    constraint=f"max_size_{limit}"
                ))

    return errors


def validate_routing_invariant(data: dict[str, Any]) -> list[ValidationError]:
    """
    Validate routing invariant for escalation receipts.
    recipient_ai must equal escalation_to when phase=escalate
    """
    errors = []

    phase = data.get("phase")
    if phase == "escalate" or phase == Phase.ESCALATE:
        recipient_ai = data.get("recipient_ai")
        escalation_to = data.get("escalation_to")

        if recipient_ai != escalation_to:
            errors.append(ValidationError(
                message="recipient_ai must equal escalation_to for escalate phase",
                field="recipient_ai",
                constraint="routing_invariant"
            ))

    return errors


def validate_receipt(data: dict[str, Any]) -> list[ValidationError]:
    """
    Validate receipt data before storage.
    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Field size validation
    errors.extend(validate_field_sizes(data))

    # Routing invariant
    errors.extend(validate_routing_invariant(data))

    return errors


def validate_receipt_create(receipt_create: ReceiptCreate, tenant_id: str) -> Receipt:
    """
    Convert ReceiptCreate to Receipt with tenant_id and generate receipt_id if needed.
    Raises ValidationError if validation fails.
    """
    from .models import generate_receipt_id

    # Pre-validate field sizes
    data = receipt_create.model_dump()
    errors = validate_receipt(data)

    if errors:
        raise ValidationError(
            message="; ".join(e.message for e in errors),
            field=errors[0].field,
            constraint=errors[0].constraint
        )

    # Build receipt with server-assigned values
    receipt_data = data.copy()
    receipt_data["tenant_id"] = tenant_id

    if not receipt_data.get("receipt_id"):
        receipt_data["receipt_id"] = generate_receipt_id()

    # This will run Pydantic model validation including phase constraints
    return Receipt(**receipt_data)

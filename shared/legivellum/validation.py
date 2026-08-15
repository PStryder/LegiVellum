"""
LegiVellum Receipt Validation

Additional validation utilities beyond Pydantic model validation.
"""
import json
import os
from pathlib import Path
from typing import Any

# Imported unguarded on purpose. This was previously wrapped in
# `except ImportError: JSONSCHEMA_AVAILABLE = False`, which turned a broken
# install into a validator that silently accepted everything -- the same
# fail-open shape the schema-path handling above exists to prevent. A component
# that cannot validate receipts must fail to start, loudly, naming the
# dependency.
import jsonschema

from .models import Phase, Receipt, ReceiptCreate


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


def validate_phase_constraints(data: dict[str, Any]) -> list[ValidationError]:
    """
    Validate phase-specific constraints for partially-populated receipts.
    Only checks fields present in the payload.
    """
    errors: list[ValidationError] = []
    phase = data.get("phase")
    if not phase:
        return errors

    try:
        phase_value = Phase(phase) if not isinstance(phase, Phase) else phase
    except ValueError:
        return errors

    def _error(message: str, field: str, constraint: str) -> None:
        errors.append(ValidationError(message=message, field=field, constraint=constraint))

    if phase_value == Phase.ACCEPTED:
        status = data.get("status")
        if status is not None and status != "NA":
            _error("status must be 'NA' for accepted phase", "status", "phase_accepted")
        if "completed_at" in data and data.get("completed_at") is not None:
            _error("completed_at must be null for accepted phase", "completed_at", "phase_accepted")
        if data.get("task_summary") == "TBD":
            _error("task_summary must not be 'TBD' for accepted phase", "task_summary", "phase_accepted")
        outcome_kind = data.get("outcome_kind")
        if outcome_kind is not None and outcome_kind != "NA":
            _error("outcome_kind must be 'NA' for accepted phase", "outcome_kind", "phase_accepted")
        escalation_class = data.get("escalation_class")
        if escalation_class is not None and escalation_class != "NA":
            _error("escalation_class must be 'NA' for accepted phase", "escalation_class", "phase_accepted")

    elif phase_value == Phase.COMPLETE:
        status = data.get("status")
        if status is not None and status not in ("success", "failure", "canceled"):
            _error(
                "status must be 'success', 'failure', or 'canceled' for complete phase",
                "status",
                "phase_complete",
            )
        if "completed_at" in data and data.get("completed_at") is None:
            _error("completed_at is required for complete phase", "completed_at", "phase_complete")
        outcome_kind = data.get("outcome_kind")
        if outcome_kind is not None and outcome_kind in ("NA", "TBD"):
            _error("outcome_kind must be a valid value for complete phase", "outcome_kind", "phase_complete")
        escalation_class = data.get("escalation_class")
        if escalation_class is not None and escalation_class != "NA":
            _error("escalation_class must be 'NA' for complete phase", "escalation_class", "phase_complete")

    elif phase_value == Phase.ESCALATE:
        status = data.get("status")
        if status is not None and status != "NA":
            _error("status must be 'NA' for escalate phase", "status", "phase_escalate")
        escalation_class = data.get("escalation_class")
        if escalation_class is not None and escalation_class in ("NA", "TBD"):
            _error(
                "escalation_class must be a valid escalation value for escalate phase",
                "escalation_class",
                "phase_escalate",
            )
        escalation_reason = data.get("escalation_reason")
        if escalation_reason is not None and escalation_reason in ("NA", "TBD"):
            _error("escalation_reason must be provided for escalate phase", "escalation_reason", "phase_escalate")
        escalation_to = data.get("escalation_to")
        if escalation_to is not None and escalation_to == "NA":
            _error("escalation_to is required for escalate phase", "escalation_to", "phase_escalate")
        recipient_ai = data.get("recipient_ai")
        if escalation_to is not None and recipient_ai is not None and recipient_ai != escalation_to:
            _error(
                "recipient_ai must equal escalation_to for escalate phase",
                "recipient_ai",
                "phase_escalate",
            )

    # Retry rule (only if both provided)
    if data.get("retry_requested") and data.get("attempt", 0) < 1:
        _error("attempt must be >= 1 when retry_requested is true", "attempt", "retry_requested")

    return errors


def validate_receipt(data: dict[str, Any], *, validate_schema: bool = True) -> list[ValidationError]:
    """
    Validate receipt data before storage.
    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Field size validation
    errors.extend(validate_field_sizes(data))

    # Phase-specific constraints
    errors.extend(validate_phase_constraints(data))

    # Routing invariant
    errors.extend(validate_routing_invariant(data))

    # Canonical JSON Schema. No availability gate: jsonschema is a hard
    # dependency and a missing schema raises rather than passing everything.
    if validate_schema:
        errors.extend(validate_json_schema(data))

    return errors


SCHEMA_FILENAME = "receipt.schema.v1.json"
SCHEMA_DIR_ENV = "LEGIVELLUM_SCHEMA_DIR"

_schema_cache: dict[str, Any] | None = None


def schema_path() -> Path:
    """Locate the canonical receipt schema, package copy first.

    Resolution order, and why:

    1. ``LEGIVELLUM_SCHEMA_DIR`` — an operator override, so a deployment can
       point at a pinned schema without reinstalling.
    2. ``legivellum/schemas/`` inside the installed package. This is the one
       that works in a container, where no repository checkout exists.
    3. ``docs/canonical/`` relative to a source checkout, for development.

    The previous implementation looked only for ``spec/receipt.schema.v1.json``
    — a directory renamed to ``docs/canonical/`` — and returned no errors when
    it was missing. Every phase rule in receipt.rules.md was therefore
    unenforced in every deployment while passing in a source checkout.
    """
    override = os.environ.get(SCHEMA_DIR_ENV)
    if override:
        candidate = Path(override) / SCHEMA_FILENAME
        if candidate.exists():
            return candidate
        raise RuntimeError(
            f"{SCHEMA_DIR_ENV} is set to {override!r} but {candidate} does not exist"
        )

    packaged = Path(__file__).resolve().parent / "schemas" / SCHEMA_FILENAME
    if packaged.exists():
        return packaged

    # Source checkout: shared/legivellum/ -> shared/ -> repo root.
    checkout = Path(__file__).resolve().parents[2] / "docs" / "canonical" / SCHEMA_FILENAME
    if checkout.exists():
        return checkout

    raise RuntimeError(
        f"Canonical receipt schema {SCHEMA_FILENAME} not found. Looked in the "
        f"installed package at {packaged} and the source checkout at {checkout}. "
        f"A validator that cannot find its rules is misconfigured, not permissive; "
        f"refusing to treat every receipt as valid."
    )


def load_schema() -> dict[str, Any]:
    """Load and cache the canonical receipt schema."""
    global _schema_cache
    if _schema_cache is None:
        with open(schema_path(), encoding="utf-8") as handle:
            _schema_cache = json.load(handle)
    return _schema_cache


def validate_json_schema(data: dict[str, Any]) -> list[ValidationError]:
    """Validate a receipt payload against the canonical JSON Schema.

    Returns a list of errors; an empty list means the payload conformed.

    This function does not fail open. If the schema cannot be located,
    ``schema_path()`` raises rather than returning "no errors" — a validator
    that reports success because it could not find its rules is worse than one
    that is absent, because callers believe validation happened.
    """
    errors: list[ValidationError] = []
    schema = load_schema()

    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        errors.append(
            ValidationError(
                message=f"JSON Schema validation failed: {exc.message}",
                field=".".join(str(p) for p in exc.path) if exc.path else "unknown",
                constraint="json_schema",
            )
        )

    return errors


def validate_receipt_create(receipt_create: ReceiptCreate, tenant_id: str) -> Receipt:
    """
    Convert ReceiptCreate to Receipt with tenant_id and generate receipt_id if needed.
    Raises ValidationError if validation fails.
    """
    from .models import generate_receipt_id

    # Pre-validate field sizes
    data = receipt_create.model_dump()
    errors = validate_receipt(data, validate_schema=False)

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

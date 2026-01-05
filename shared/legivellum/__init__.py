# LegiVellum Shared Library
# Common models, schemas, and utilities for the LegiVellum system
__version__ = "0.1.0"

from .models import Receipt, Phase, Status, OutcomeKind, EscalationClass
from .validation import validate_receipt

__all__ = [
    "Receipt",
    "Phase",
    "Status",
    "OutcomeKind",
    "EscalationClass",
    "validate_receipt",
]

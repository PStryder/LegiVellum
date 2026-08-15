"""LegiVellum — the receipt protocol, and the control plane built on it.

Importing this package must not require the control plane's dependency tree.

Until now it did: `__init__.py` eagerly imported `problemata_control`
(SQLAlchemy), `problemata_control_ui` (FastAPI) and `problemata_publish`, so
`from legivellum.models import Receipt` — the one line a gate needs in order to
validate a receipt — pulled in the whole application stack. Gates do not install
that stack, so the import raised `ModuleNotFoundError`, and every emitter caught
it and fell back to posting unvalidated dictionaries. Canonical validation was
off in production across the stack and nothing said so.

The split is therefore load-bearing, not tidiness:

    protocol   models, validation, ulid    pydantic + jsonschema
    control    problemata_*, observability  sqlalchemy, fastapi, prometheus
    bootstrap  metagate_bootstrap           httpx

Protocol names are imported eagerly, because a component that cannot import
them must fail loudly rather than continue unvalidated. Everything else is
resolved on first attribute access via PEP 562, so `import legivellum` costs
pydantic and nothing more, and a missing control-plane dependency surfaces at
the point of use naming the module that needs it.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"

# Protocol surface. Light by construction: pydantic for models, jsonschema for
# validation. Eager on purpose -- see the module docstring.
from .models import EscalationClass, OutcomeKind, Phase, Receipt, Status
from .ulid import is_ulid, new_ulid
from .validation import validate_receipt

# name -> module it lives in. Resolved lazily so the control-plane and
# bootstrap dependency trees are only paid for by callers that use them.
_LAZY: dict[str, str] = {
    "validate_problemata_spec": "problemata_validation",
    "ProblemataValidationError": "problemata_validation",
    "ProblemataValidationResult": "problemata_validation",
    "ValidationLayer": "problemata_validation",
    "ValidationContext": "problemata_validation",
    "apply_problemata_migrations": "problemata_control",
    "AsyncProblemataControlService": "problemata_control",
    "compile_problemata_blueprint": "problemata_control",
    "create_default_postgres_problemata_service": "problemata_control",
    "InMemoryProblemataRepository": "problemata_control",
    "PostgresProblemataRepository": "problemata_control",
    "ProblemataBlueprint": "problemata_control",
    "ProblemataControlService": "problemata_control",
    "ProblemataDiagnosticsResult": "problemata_control",
    "ProblemataDiagnosticsStatus": "problemata_control",
    "ProblemataEdgeDiagnostic": "problemata_control",
    "ProblemataRecord": "problemata_control",
    "ProblemataStatus": "problemata_control",
    "ProblemataTopologyNode": "problemata_control",
    "MetaGatePublisher": "problemata_publish",
    "ProblemataPublishError": "problemata_publish",
    "BootstrapResult": "metagate_bootstrap",
    "EndpointBinding": "metagate_bootstrap",
    "acknowledge_startup": "metagate_bootstrap",
    "bootstrap_from_metagate": "metagate_bootstrap",
    "endpoint_for_type": "metagate_bootstrap",
}

# Exported under a different name than the module defines it.
_LAZY_ALIASES: dict[str, tuple[str, str]] = {
    "create_problemata_control_ui_app": ("problemata_control_ui", "create_app"),
}


def __getattr__(name: str) -> Any:
    """Resolve control-plane and bootstrap names on first use (PEP 562)."""
    import importlib

    if name in _LAZY_ALIASES:
        module_name, attribute = _LAZY_ALIASES[name]
    elif name in _LAZY:
        module_name, attribute = _LAZY[name], name
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    try:
        module = importlib.import_module(f".{module_name}", __name__)
    except ImportError as exc:
        # Name the dependency rather than letting it read as a missing symbol.
        raise ImportError(
            f"legivellum.{name} requires the '{module_name}' module, whose "
            f"dependencies are not installed. Install the control-plane extra: "
            f"pip install 'legivellum[control-plane]'. Original error: {exc}"
        ) from exc
    return getattr(module, attribute)


def __dir__() -> list[str]:
    return sorted(__all__)


__all__ = [
    # protocol
    "Receipt",
    "Phase",
    "Status",
    "OutcomeKind",
    "EscalationClass",
    "validate_receipt",
    "new_ulid",
    "is_ulid",
    # control plane (lazy)
    *sorted(_LAZY),
    *sorted(_LAZY_ALIASES),
]

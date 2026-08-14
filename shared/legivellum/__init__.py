# LegiVellum Shared Library
# Common models, schemas, and utilities for the LegiVellum system
__version__ = "0.1.0"

from .models import Receipt, Phase, Status, OutcomeKind, EscalationClass
from .validation import validate_receipt
from .problemata_validation import (
    validate_problemata_spec,
    ProblemataValidationError,
    ProblemataValidationResult,
    ValidationLayer,
    ValidationContext,
)
from .problemata_control import (
    apply_problemata_migrations,
    AsyncProblemataControlService,
    compile_problemata_blueprint,
    create_default_postgres_problemata_service,
    InMemoryProblemataRepository,
    PostgresProblemataRepository,
    ProblemataBlueprint,
    ProblemataControlService,
    ProblemataDiagnosticsResult,
    ProblemataDiagnosticsStatus,
    ProblemataEdgeDiagnostic,
    ProblemataRecord,
    ProblemataStatus,
    ProblemataTopologyNode,
)
from .problemata_control_ui import create_app as create_problemata_control_ui_app
from .problemata_publish import MetaGatePublisher, ProblemataPublishError
from .metagate_bootstrap import (
    BootstrapResult,
    EndpointBinding,
    acknowledge_startup,
    bootstrap_from_metagate,
    endpoint_for_type,
)

__all__ = [
    "Receipt",
    "Phase",
    "Status",
    "OutcomeKind",
    "EscalationClass",
    "validate_receipt",
    "validate_problemata_spec",
    "ProblemataValidationError",
    "ProblemataValidationResult",
    "ValidationLayer",
    "ValidationContext",
    "apply_problemata_migrations",
    "AsyncProblemataControlService",
    "compile_problemata_blueprint",
    "create_default_postgres_problemata_service",
    "InMemoryProblemataRepository",
    "PostgresProblemataRepository",
    "ProblemataBlueprint",
    "ProblemataControlService",
    "ProblemataDiagnosticsResult",
    "ProblemataDiagnosticsStatus",
    "ProblemataEdgeDiagnostic",
    "ProblemataRecord",
    "ProblemataStatus",
    "ProblemataTopologyNode",
    "create_problemata_control_ui_app",
    "MetaGatePublisher",
    "ProblemataPublishError",
    "BootstrapResult",
    "EndpointBinding",
    "acknowledge_startup",
    "bootstrap_from_metagate",
    "endpoint_for_type",
]

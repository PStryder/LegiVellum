"""
Problemata validation skeleton for LegiVellum.

Implements atomic validation with structured errors per
docs/canonical/problemata.validation.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Optional

from pydantic import BaseModel, Field

VALIDATOR_VERSION = "0.1.0"


class ValidationLayer(str, Enum):
    """Validation layers per canonical contract."""

    STRUCTURAL = "structural"
    CONFIGURATION = "configuration"
    SEMANTIC = "semantic"
    SECURITY = "security"


class ProblemataValidationError(BaseModel):
    """Structured validation error."""

    code: str
    layer: ValidationLayer
    path: str
    message: str
    hint: Optional[str] = None


class ProblemataValidationResult(BaseModel):
    """Validation result envelope (schema v1)."""

    status: str = Field(default="passed", pattern="^(passed|failed)$")
    errors: list[ProblemataValidationError] = Field(default_factory=list)
    spec_version: Optional[str] = None
    validator_version: str = VALIDATOR_VERSION
    validated_by: Optional[str] = None
    spec_hash: Optional[str] = None
    report_pointer: Optional[str] = None


@dataclass
class ValidationContext:
    """Context hooks for external resolution."""

    secret_resolver: Optional[Callable[[str], bool]] = None
    profile_resolver: Optional[Callable[[str], bool]] = None
    validated_by: Optional[str] = None
    report_pointer: Optional[str] = None


REQUIRED_PRIMITIVE_TYPES = {"metagate", "receiptgate", "depotgate"}

# Required config keys per primitive type (v0).
PRIMITIVE_REQUIRED_CONFIG: dict[str, list[str]] = {
    "receiptgate": ["receipt_schema_version"],
    "depotgate": ["default_sink"],
    "asyncgate": [
        "lease_ttl_seconds",
        "max_attempts",
        "retry_backoff_seconds",
        "receipt_mode",
        "receiptgate_ref",
    ],
    "cognigate": [
        "ai.endpoint",
        "ai.model",
        "ai.api_key_ref",
        "receiptgate_ref",
        "depotgate_ref",
    ],
    "delegate": [
        "planner.model",
        "planner.api_key_ref",
        "plan_store_ref",
        "receiptgate_ref",
    ],
    "delegategate": [
        "planner.model",
        "planner.api_key_ref",
        "plan_store_ref",
        "receiptgate_ref",
    ],
    "interrogate": [
        "policy_profile_id",
        "metagate_ref",
    ],
    "interview": [
        "allowed_sources",
        "rate_limits",
    ],
    "worker": [
        "capabilities",
        "receiptgate_ref",
        "depotgate_ref",
    ],
}

# Primitive types that must emit receipts and store artifacts by default.
RECEIPT_EMITTER_TYPES = {
    "asyncgate",
    "cognigate",
    "delegate",
    "delegategate",
    "interrogate",
    "worker",
}

ARTIFACT_PRODUCER_TYPES = {
    "cognigate",
    "delegate",
    "delegategate",
    "worker",
}


def validate_problemata_spec(
    spec: dict[str, Any],
    *,
    fail_fast: bool = True,
    context: ValidationContext | None = None,
) -> ProblemataValidationResult:
    """
    Validate a problemata spec with atomic semantics.

    This is a v0 skeleton: structural + minimal config + basic semantic checks.
    """
    context = context or ValidationContext()
    errors: list[ProblemataValidationError] = []

    spec_version = _get_spec_version(spec)
    spec_hash = _hash_spec(spec)

    def _extend(new_errors: Iterable[ProblemataValidationError]) -> bool:
        new_list = list(new_errors)
        if new_list:
            errors.extend(new_list)
            return True
        return False

    if _extend(_validate_structural(spec)) and fail_fast:
        return _result(errors, spec_version, spec_hash, context)

    if _extend(_validate_configuration(spec, context)) and fail_fast:
        return _result(errors, spec_version, spec_hash, context)

    if _extend(_validate_semantic(spec)) and fail_fast:
        return _result(errors, spec_version, spec_hash, context)

    if _extend(_validate_security(spec, context)) and fail_fast:
        return _result(errors, spec_version, spec_hash, context)

    return _result(errors, spec_version, spec_hash, context)


def _result(
    errors: list[ProblemataValidationError],
    spec_version: Optional[str],
    spec_hash: Optional[str],
    context: ValidationContext,
) -> ProblemataValidationResult:
    status = "failed" if errors else "passed"
    return ProblemataValidationResult(
        status=status,
        errors=errors,
        spec_version=spec_version,
        validator_version=VALIDATOR_VERSION,
        validated_by=context.validated_by,
        spec_hash=spec_hash,
        report_pointer=context.report_pointer,
    )


def _get_spec_version(spec: dict[str, Any]) -> Optional[str]:
    meta = spec.get("problemata")
    if isinstance(meta, dict):
        return meta.get("version")
    return None


def _hash_spec(spec: dict[str, Any]) -> Optional[str]:
    try:
        payload = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    except TypeError:
        payload = json.dumps(spec, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_type(value: Any) -> str:
    return str(value or "").strip().lower()


def _validate_structural(spec: dict[str, Any]) -> list[ProblemataValidationError]:
    errors: list[ProblemataValidationError] = []
    primitives = spec.get("primitives")

    if not isinstance(primitives, dict) or not primitives:
        errors.append(
            ProblemataValidationError(
                code="PMV-STRUCT-001",
                layer=ValidationLayer.STRUCTURAL,
                path="primitives",
                message="primitives must be a non-empty map",
                hint="Define component instances keyed by id",
            )
        )
        return errors

    types_present = {_normalize_type(item.get("type")) for item in primitives.values() if isinstance(item, dict)}
    for required in REQUIRED_PRIMITIVE_TYPES:
        if required not in types_present:
            errors.append(
                ProblemataValidationError(
                    code="PMV-STRUCT-001",
                    layer=ValidationLayer.STRUCTURAL,
                    path="primitives",
                    message=f"Missing required primitive type: {required}",
                    hint=f"Add a {required} instance to primitives",
                )
            )

    edges = spec.get("topology") or []
    if not isinstance(edges, list):
        errors.append(
            ProblemataValidationError(
                code="PMV-STRUCT-002",
                layer=ValidationLayer.STRUCTURAL,
                path="topology",
                message="topology must be a list of edges",
                hint="Provide a list of edge objects with from/to/purpose",
            )
        )
        return errors

    primitive_ids = set(primitives.keys())
    referenced: set[str] = set()

    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(
                ProblemataValidationError(
                    code="PMV-STRUCT-002",
                    layer=ValidationLayer.STRUCTURAL,
                    path=f"topology[{idx}]",
                    message="Topology edge must be an object",
                )
            )
            continue

        from_id = edge.get("from")
        to_id = edge.get("to")

        if from_id not in primitive_ids:
            errors.append(
                ProblemataValidationError(
                    code="PMV-STRUCT-002",
                    layer=ValidationLayer.STRUCTURAL,
                    path=f"topology[{idx}].from",
                    message=f"Edge references missing component: {from_id}",
                )
            )
        else:
            referenced.add(from_id)

        if to_id not in primitive_ids:
            errors.append(
                ProblemataValidationError(
                    code="PMV-STRUCT-002",
                    layer=ValidationLayer.STRUCTURAL,
                    path=f"topology[{idx}].to",
                    message=f"Edge references missing component: {to_id}",
                )
            )
        else:
            referenced.add(to_id)

        protocol = edge.get("protocol")
        if protocol and str(protocol).strip().lower() != "mcp":
            errors.append(
                ProblemataValidationError(
                    code="PMV-STRUCT-005",
                    layer=ValidationLayer.STRUCTURAL,
                    path=f"topology[{idx}].protocol",
                    message="Unsupported protocol (non-MCP)",
                    hint="Use protocol: mcp or omit to default to MCP",
                )
            )

    for primitive_id in primitive_ids:
        if primitive_id not in referenced:
            errors.append(
                ProblemataValidationError(
                    code="PMV-STRUCT-003",
                    layer=ValidationLayer.STRUCTURAL,
                    path=f"primitives.{primitive_id}",
                    message="Orphaned component (not referenced in topology)",
                    hint="Add topology edges or remove the component",
                )
            )

    if _has_bootstrap_cycle(edges):
        errors.append(
            ProblemataValidationError(
                code="PMV-STRUCT-004",
                layer=ValidationLayer.STRUCTURAL,
                path="topology.bootstrap",
                message="Circular bootstrap dependency detected",
                hint="Remove cycles in bootstrap edges",
            )
        )

    return errors


def _validate_configuration(
    spec: dict[str, Any],
    context: ValidationContext,
) -> list[ProblemataValidationError]:
    errors: list[ProblemataValidationError] = []
    primitives = spec.get("primitives")
    defaults = {}
    meta = spec.get("problemata")
    if isinstance(meta, dict):
        defaults = meta.get("defaults") or {}
        if not isinstance(defaults, dict):
            defaults = {}

    if not isinstance(primitives, dict):
        return errors

    for primitive_id, primitive in primitives.items():
        if not isinstance(primitive, dict):
            continue

        primitive_type = _normalize_type(primitive.get("type"))
        config = primitive.get("config")
        endpoint = primitive.get("endpoint")

        if not isinstance(endpoint, str) or not endpoint.strip():
            errors.append(
                ProblemataValidationError(
                    code="PMV-CONFIG-003",
                    layer=ValidationLayer.CONFIGURATION,
                    path=f"primitives.{primitive_id}.endpoint",
                    message="Endpoint must be a non-empty string",
                )
            )

        if not isinstance(config, dict):
            errors.append(
                ProblemataValidationError(
                    code="PMV-CONFIG-001",
                    layer=ValidationLayer.CONFIGURATION,
                    path=f"primitives.{primitive_id}.config",
                    message="Config must be an object",
                )
            )
            continue

        # Required keys by primitive type
        for key_path in PRIMITIVE_REQUIRED_CONFIG.get(primitive_type, []):
            value = _get_nested_value(config, key_path)
            if value is None and key_path in ("receiptgate_ref", "depotgate_ref"):
                value = defaults.get(key_path)
            if value is None:
                errors.append(
                    ProblemataValidationError(
                        code="PMV-CONFIG-001",
                        layer=ValidationLayer.CONFIGURATION,
                        path=f"primitives.{primitive_id}.config.{key_path}",
                        message=f"Missing required config key: {key_path}",
                    )
                )

        # Cognigate must define profiles inline or via profile_ref
        if primitive_type == "cognigate":
            if not config.get("profiles") and not config.get("profile_ref"):
                errors.append(
                    ProblemataValidationError(
                        code="PMV-CONFIG-001",
                        layer=ValidationLayer.CONFIGURATION,
                        path=f"primitives.{primitive_id}.config.profile_ref",
                        message="CogniGate requires profiles or profile_ref",
                        hint="Set config.profiles or config.profile_ref",
                    )
                )

        # InterroGate must reference a lineage source (receiptgate preferred).
        if primitive_type == "interrogate":
            if not (config.get("receiptgate_ref") or config.get("memorygate_ref")):
                errors.append(
                    ProblemataValidationError(
                        code="PMV-CONFIG-001",
                        layer=ValidationLayer.CONFIGURATION,
                        path=f"primitives.{primitive_id}.config.receiptgate_ref",
                        message="InterroGate requires receiptgate_ref (or memorygate_ref)",
                        hint="Set config.receiptgate_ref to ReceiptGate instance id",
                    )
                )

        _validate_runtime_constraints(
            primitive_id=primitive_id,
            primitive_type=primitive_type,
            config=config,
            errors=errors,
        )

        # Resolve refs if resolvers are provided.
        if context.secret_resolver or context.profile_resolver:
            for key, value, path in _iter_ref_values(config, base_path=f"primitives.{primitive_id}.config"):
                resolver = context.profile_resolver if "profile" in key else context.secret_resolver
                if resolver and isinstance(value, str) and not resolver(value):
                    errors.append(
                        ProblemataValidationError(
                            code="PMV-CONFIG-002",
                            layer=ValidationLayer.CONFIGURATION,
                            path=path,
                            message=f"Unresolved reference: {value}",
                        )
                    )

    return errors


def _validate_runtime_constraints(
    *,
    primitive_id: str,
    primitive_type: str,
    config: dict[str, Any],
    errors: list[ProblemataValidationError],
) -> None:
    numeric_requirements = {
        "asyncgate": ["lease_ttl_seconds", "max_attempts", "retry_backoff_seconds"],
    }
    for key in numeric_requirements.get(primitive_type, []):
        value = config.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = None
        if numeric is None or numeric <= 0:
            errors.append(
                ProblemataValidationError(
                    code="PMV-CONFIG-004",
                    layer=ValidationLayer.CONFIGURATION,
                    path=f"primitives.{primitive_id}.config.{key}",
                    message=f"Invalid runtime constraint: {key} must be > 0",
                )
            )


def _validate_semantic(spec: dict[str, Any]) -> list[ProblemataValidationError]:
    errors: list[ProblemataValidationError] = []
    primitives = spec.get("primitives")
    edges = spec.get("topology") or []

    if not isinstance(primitives, dict) or not isinstance(edges, list):
        return errors

    type_by_id = {
        primitive_id: _normalize_type(primitive.get("type"))
        for primitive_id, primitive in primitives.items()
        if isinstance(primitive, dict)
    }

    metagates = {pid for pid, ptype in type_by_id.items() if ptype == "metagate"}
    receiptgates = {pid for pid, ptype in type_by_id.items() if ptype == "receiptgate"}
    depotgates = {pid for pid, ptype in type_by_id.items() if ptype == "depotgate"}

    edges_by_purpose: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        purpose = str(edge.get("purpose") or "").strip().lower()
        edges_by_purpose.setdefault(purpose, []).append(edge)

    bootstrap_edges = edges_by_purpose.get("bootstrap", [])
    receipt_edges = edges_by_purpose.get("receipt_emit", [])
    artifact_edges = edges_by_purpose.get("artifact_store", [])

    for primitive_id, primitive_type in type_by_id.items():
        # Bootstrap to MetaGate (direct edge requirement for v0).
        if primitive_type != "metagate":
            has_bootstrap = any(
                edge.get("from") == primitive_id and edge.get("to") in metagates
                for edge in bootstrap_edges
            )
            if not has_bootstrap:
                errors.append(
                    ProblemataValidationError(
                        code="PMV-SEM-003",
                        layer=ValidationLayer.SEMANTIC,
                        path=f"primitives.{primitive_id}",
                        message="Component lacks bootstrap route to MetaGate",
                        hint=f"Add topology edge: {primitive_id} -> <metagate> (bootstrap)",
                    )
                )

        # Receipt route (direct edge requirement for v0).
        if primitive_type in RECEIPT_EMITTER_TYPES:
            has_receipt = any(
                edge.get("from") == primitive_id and edge.get("to") in receiptgates
                for edge in receipt_edges
            )
            if not has_receipt:
                errors.append(
                    ProblemataValidationError(
                        code="PMV-SEM-001",
                        layer=ValidationLayer.SEMANTIC,
                        path=f"primitives.{primitive_id}",
                        message="Receipt-producing component has no route to ReceiptGate",
                        hint=f"Add topology edge: {primitive_id} -> <receiptgate> (receipt_emit)",
                    )
                )

        # Artifact route (direct edge requirement for v0).
        if primitive_type in ARTIFACT_PRODUCER_TYPES:
            has_artifact = any(
                edge.get("from") == primitive_id and edge.get("to") in depotgates
                for edge in artifact_edges
            )
            if not has_artifact:
                errors.append(
                    ProblemataValidationError(
                        code="PMV-SEM-002",
                        layer=ValidationLayer.SEMANTIC,
                        path=f"primitives.{primitive_id}",
                        message="Artifact-producing component has no route to DepotGate",
                        hint=f"Add topology edge: {primitive_id} -> <depotgate> (artifact_store)",
                    )
                )

    # Trust domain consistency check (best-effort).
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        from_id = edge.get("from")
        trust_domain = edge.get("trust_domain")
        if trust_domain and from_id in primitives:
            from_cfg = primitives[from_id].get("config") if isinstance(primitives[from_id], dict) else None
            if isinstance(from_cfg, dict) and "trust_domain" in from_cfg:
                if from_cfg["trust_domain"] != trust_domain:
                    errors.append(
                        ProblemataValidationError(
                            code="PMV-SEM-004",
                            layer=ValidationLayer.SEMANTIC,
                            path=f"topology.{from_id}",
                            message="Trust domain mismatch between component and edge",
                        )
                    )

    return errors


def _validate_security(
    spec: dict[str, Any],
    context: ValidationContext,
) -> list[ProblemataValidationError]:
    errors: list[ProblemataValidationError] = []
    if not context.secret_resolver:
        return errors

    edges = spec.get("topology") or []
    if not isinstance(edges, list):
        return errors

    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        auth_ref = edge.get("auth_ref")
        if auth_ref and not context.secret_resolver(str(auth_ref)):
            errors.append(
                ProblemataValidationError(
                    code="PMV-SEC-001",
                    layer=ValidationLayer.SECURITY,
                    path=f"topology[{idx}].auth_ref",
                    message=f"Auth ref unresolved: {auth_ref}",
                )
            )

    return errors


def _get_nested_value(config: dict[str, Any], key_path: str) -> Any:
    current: Any = config
    for part in key_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _iter_ref_values(obj: Any, base_path: str) -> Iterable[tuple[str, Any, str]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{base_path}.{key}"
            if key.endswith("_ref"):
                yield key, value, path
            if isinstance(value, (dict, list)):
                yield from _iter_ref_values(value, path)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            path = f"{base_path}[{idx}]"
            if isinstance(value, (dict, list)):
                yield from _iter_ref_values(value, path)


def _has_bootstrap_cycle(edges: list[dict[str, Any]]) -> bool:
    graph: dict[str, set[str]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        if str(edge.get("purpose") or "").strip().lower() != "bootstrap":
            continue
        source = edge.get("from")
        target = edge.get("to")
        if not source or not target:
            continue
        graph.setdefault(source, set()).add(target)

    visited: dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=done

    def visit(node: str) -> bool:
        state = visited.get(node, 0)
        if state == 1:
            return True
        if state == 2:
            return False
        visited[node] = 1
        for neighbor in graph.get(node, set()):
            if visit(neighbor):
                return True
        visited[node] = 2
        return False

    for node in graph:
        if visit(node):
            return True
    return False

"""Shared MetaGate bootstrap client for LegiVellum primitives.

Every alignment note lists "bootstrap config from MetaGate" as required
contract behaviour. AsyncGate implemented it first; this is that implementation
generalized so the remaining gates do not each grow their own copy. The four
identical `parents[4]` IndexErrors fixed across four repos are what duplicated
integration code looks like a few months on.

Gates differ only in which primitive types they care about, so that is the one
thing they declare:

    BOOTSTRAP_BINDINGS = (
        EndpointBinding(primitive_type="receiptgate", setting="receiptgate_endpoint"),
    )
    result = await bootstrap_from_metagate(settings, bindings=BOOTSTRAP_BINDINGS)

Two properties are load-bearing and belong here rather than in each caller:

Bootstrap must never prevent startup. MetaGate is a describe-only, non-blocking
authority, not a dependency to wait on. Every failure -- unreachable, timeout,
auth rejected, no binding, malformed packet -- degrades to a logged warning and
"carry on with configured values". A bootstrap authority that can take the mesh
down is a hidden master, which the architecture forbids.

Explicit configuration wins. An operator who set an endpoint said something
specific; bootstrap fills gaps and never overrides intent, though it logs when
the mesh disagrees so the divergence is visible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_BUILD_VERSION = "0.1.0"


@dataclass(frozen=True)
class EndpointBinding:
    """Maps a primitive type in the manifest to a settings attribute.

    Keyed by *type* rather than service ref: refs are Problemata-authored names
    ("receiptgate-main"), while types are contract vocabulary and stable across
    every Problemata that declares the primitive.
    """

    primitive_type: str
    setting: str


@dataclass
class BootstrapResult:
    """Outcome of a bootstrap attempt.

    Never raised, always returned: callers treat failure as "carry on", so the
    reason is data rather than control flow.
    """

    attempted: bool
    succeeded: bool
    reason: Optional[str] = None
    manifest: Optional[str] = None
    services: dict[str, Any] = field(default_factory=dict)
    applied: dict[str, str] = field(default_factory=dict)
    startup_id: Optional[str] = None


def _same_endpoint(a: Optional[str], b: Optional[str]) -> bool:
    """Compare endpoints ignoring a trailing /mcp and trailing slashes.

    Callers append /mcp when invoking, so "http://receiptgate:8000" and
    "http://receiptgate:8000/mcp" address the same service. Comparing them
    literally reports a divergence that does not exist, which trains operators
    to ignore a log line that is supposed to mean something.
    """
    def _canonical(value: Optional[str]) -> str:
        if not value:
            return ""
        trimmed = value.rstrip("/")
        if trimmed.endswith("/mcp"):
            trimmed = trimmed[: -len("/mcp")]
        return trimmed.rstrip("/")

    return _canonical(a) == _canonical(b)


def endpoint_for_type(services: Any, primitive_type: str) -> Optional[str]:
    """Return the first endpoint whose service declares the given type.

    Tolerates a malformed services block rather than raising: a bootstrap packet
    is external input, and a wrong shape should read as "nothing to apply", not
    surface as an AttributeError in the failure reason.
    """
    if not isinstance(services, dict):
        return None
    for service in services.values():
        if not isinstance(service, dict):
            continue
        if service.get("type") != primitive_type:
            continue
        endpoint = service.get("endpoint") or service.get("url")
        if isinstance(endpoint, str) and endpoint:
            return endpoint
    return None


async def _mcp_call(
    client: httpx.AsyncClient,
    endpoint: str,
    tool: str,
    arguments: dict[str, Any],
    *,
    api_key: Optional[str],
) -> dict[str, Any]:
    url = endpoint if endpoint.endswith("/mcp") else f"{endpoint.rstrip('/')}/mcp"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    response = await client.post(
        url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        headers=headers,
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(f"{tool}: {body['error']}")
    result = body.get("result")
    if result is None:
        raise RuntimeError(f"{tool} returned no result")
    return result


async def bootstrap_from_metagate(
    settings: Any,
    *,
    bindings: Sequence[EndpointBinding],
    component_key: Optional[str] = None,
) -> BootstrapResult:
    """Resolve peer endpoints from MetaGate, filling only what is unset.

    Mutates `settings` in place for the values it resolves and returns a
    BootstrapResult. Never raises.
    """
    endpoint = getattr(settings, "metagate_endpoint", None)
    if not endpoint:
        return BootstrapResult(
            attempted=False, succeeded=False, reason="metagate_endpoint not configured"
        )

    resolved_component = (
        component_key
        or getattr(settings, "metagate_component_key", None)
        or "component"
    )
    api_key = getattr(settings, "metagate_api_key", None)
    timeout = getattr(settings, "metagate_bootstrap_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            result = await _mcp_call(
                client,
                endpoint,
                "metagate.bootstrap",
                {"component_key": resolved_component},
                api_key=api_key,
            )
            packet = result.get("packet", result)
            if not isinstance(packet, dict):
                raise RuntimeError(f"bootstrap packet is not an object: {type(packet).__name__}")

            services = packet.get("services") or {}
            manifest = packet.get("manifest")

            applied: dict[str, str] = {}
            for binding in bindings:
                discovered = endpoint_for_type(services, binding.primitive_type)
                if not discovered:
                    continue
                current = getattr(settings, binding.setting, None)
                if not current:
                    setattr(settings, binding.setting, discovered)
                    applied[binding.setting] = discovered
                elif not _same_endpoint(current, discovered):
                    logger.info(
                        "metagate_bootstrap_endpoint_override setting=%s configured=%s manifest=%s",
                        binding.setting,
                        current,
                        discovered,
                    )

            startup = packet.get("startup")
            startup_id = startup.get("startup_id") if isinstance(startup, dict) else None

            logger.info(
                "metagate_bootstrap_ok component=%s manifest=%s services=%d applied=%s",
                resolved_component,
                manifest,
                len(services) if isinstance(services, dict) else 0,
                sorted(applied) or "none",
            )
            return BootstrapResult(
                attempted=True,
                succeeded=True,
                manifest=manifest,
                services=services if isinstance(services, dict) else {},
                applied=applied,
                startup_id=startup_id,
            )
    except Exception as exc:  # noqa: BLE001 - bootstrap must never take startup down
        logger.warning(
            "metagate_bootstrap_failed component=%s endpoint=%s error=%s; "
            "continuing with configured values",
            resolved_component,
            endpoint,
            exc,
        )
        return BootstrapResult(attempted=True, succeeded=False, reason=str(exc))


async def acknowledge_startup(settings: Any, result: BootstrapResult) -> bool:
    """Close the startup session MetaGate opened during bootstrap.

    perform_bootstrap opens a session with a deadline; never acking leaves it
    open until expiry and makes MetaGate's view of the mesh wrong. Failing to
    ack is not worth taking startup down for either.
    """
    if not result.succeeded or not result.startup_id:
        return False

    endpoint = getattr(settings, "metagate_endpoint", None)
    if not endpoint:
        return False
    api_key = getattr(settings, "metagate_api_key", None)
    timeout = getattr(settings, "metagate_bootstrap_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    build_version = getattr(settings, "build_version", None) or DEFAULT_BUILD_VERSION

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await _mcp_call(
                client,
                endpoint,
                "metagate.startup_ready",
                # build_version is required by the contract: MetaGate records it
                # on the session and in the startup receipt it emits.
                {"startup_id": result.startup_id, "build_version": build_version},
                api_key=api_key,
            )
        logger.info("metagate_startup_acknowledged startup_id=%s", result.startup_id)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "metagate_startup_ack_failed startup_id=%s error=%s", result.startup_id, exc
        )
        return False

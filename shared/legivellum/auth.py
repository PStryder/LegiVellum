"""
LegiVellum Authentication Utilities

Shared auth utilities for extracting tenant_id from requests.
MVP: API key auth with local-dev bypass modes for integration velocity.
"""

from __future__ import annotations

import os

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

# API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Auth token header (for future JWT support)
auth_header = APIKeyHeader(name="Authorization", auto_error=False)

# MVP: Simple API key to tenant_id mapping
# In production, this would be a database lookup or JWT claim extraction.
API_KEY_TENANT_MAP = {
    "dev-key-pstryder": "pstryder",
    "dev-key-alice": "alice",
    "dev-key-bob": "bob",
    "test-key": "test",
}

LOCALHOST_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
AUTH_MODE_STRICT = "strict"
AUTH_MODE_AUTO = "auto"
AUTH_MODE_OPTIONAL = "optional"
AUTH_MODE_DISABLED = "disabled"
AUTH_MODE_ALIASES = {
    "strict": AUTH_MODE_STRICT,
    "required": AUTH_MODE_STRICT,
    "auto": AUTH_MODE_AUTO,
    "dev": AUTH_MODE_AUTO,
    "optional": AUTH_MODE_OPTIONAL,
    "disabled": AUTH_MODE_DISABLED,
    "off": AUTH_MODE_DISABLED,
    "none": AUTH_MODE_DISABLED,
}


def get_auth_mode() -> str:
    """Resolve auth mode from environment."""
    raw_mode = os.environ.get("LEGIVELLUM_AUTH_MODE", AUTH_MODE_AUTO).strip().lower()
    return AUTH_MODE_ALIASES.get(raw_mode, AUTH_MODE_AUTO)


def get_default_tenant_id() -> str:
    """Tenant returned when auth bypass mode applies."""
    return os.environ.get("LEGIVELLUM_DEFAULT_TENANT") or os.environ.get("LEGIVELLUM_TENANT_ID", "pstryder")


def _iter_env_tenant_api_keys() -> dict[str, str]:
    """
    Parse dynamic tenant keys from environment.

    Format:
    - TENANT_API_KEY_<tenant_id>=<api_key>
    """
    prefix = "TENANT_API_KEY_"
    dynamic_map: dict[str, str] = {}
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        tenant_id = env_key[len(prefix):].strip().lower()
        api_key = env_value.strip()
        if tenant_id and api_key:
            dynamic_map[api_key] = tenant_id
    return dynamic_map


def _tenant_from_key_pattern(api_key: str) -> str | None:
    """Allow dynamic test/dev key formats without static registration."""
    for prefix in ("dev-key-", "test-key-"):
        if api_key.startswith(prefix):
            tenant_id = api_key[len(prefix):].strip()
            if tenant_id:
                return tenant_id
    return None


def get_tenant_from_api_key(api_key: str) -> str | None:
    """Map API key to tenant_id."""
    if not api_key:
        return None

    normalized_key = api_key.strip()
    if not normalized_key:
        return None

    # Check environment variable for default key.
    env_key = os.environ.get("LEGIVELLUM_API_KEY")
    env_tenant = os.environ.get("LEGIVELLUM_TENANT_ID", "pstryder")
    if env_key and normalized_key == env_key:
        return env_tenant

    mapped_tenant = API_KEY_TENANT_MAP.get(normalized_key)
    if mapped_tenant:
        return mapped_tenant

    patterned_tenant = _tenant_from_key_pattern(normalized_key)
    if patterned_tenant:
        return patterned_tenant

    return _iter_env_tenant_api_keys().get(normalized_key)


def get_tenant_from_bearer(auth_value: str) -> str | None:
    """
    Extract tenant_id from Bearer token.
    MVP: Treats Bearer token as API key.
    Production: Would validate JWT and extract tenant claim.
    """
    if not auth_value:
        return None

    if auth_value.startswith("Bearer "):
        token = auth_value[7:]
        return get_tenant_from_api_key(token)

    return None


def _resolve_tenant_from_headers(
    *,
    api_key: str | None,
    authorization: str | None,
) -> str | None:
    if api_key:
        tenant_id = get_tenant_from_api_key(api_key)
        if tenant_id:
            return tenant_id

    if authorization:
        tenant_id = get_tenant_from_bearer(authorization)
        if tenant_id:
            return tenant_id

    return None


def _is_local_request(request: Request | None) -> bool:
    if request is None:
        return False

    hosts: list[str] = []
    if request.client and request.client.host:
        hosts.append(request.client.host)

    host_header = request.headers.get("host")
    if host_header:
        hosts.append(host_header.split(":")[0])

    if request.url and request.url.hostname:
        hosts.append(request.url.hostname)

    return any(host.strip().lower() in LOCALHOST_HOSTS for host in hosts if host)


def _should_bypass_auth(request: Request | None) -> bool:
    mode = get_auth_mode()
    if mode in {AUTH_MODE_OPTIONAL, AUTH_MODE_DISABLED}:
        return True
    if mode == AUTH_MODE_AUTO and _is_local_request(request):
        return True
    return False


async def get_current_tenant(
    api_key: str | None = Security(api_key_header),
    authorization: str | None = Security(auth_header),
    request: Request = None,
) -> str:
    """
    FastAPI dependency to extract tenant_id from request.

    Checks:
    1. X-API-Key header
    2. Authorization: Bearer <token> header
    3. Optional local bypass (mode-driven)

    Returns tenant_id or raises 401.
    """
    tenant_id = _resolve_tenant_from_headers(api_key=api_key, authorization=authorization)
    if tenant_id:
        return tenant_id

    if _should_bypass_auth(request):
        return get_default_tenant_id()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_tenant(
    api_key: str | None = Security(api_key_header),
    authorization: str | None = Security(auth_header),
    request: Request = None,
) -> str | None:
    """
    Optional tenant extraction.
    Returns tenant_id when valid auth exists, or default tenant if bypass mode applies.
    """
    tenant_id = _resolve_tenant_from_headers(api_key=api_key, authorization=authorization)
    if tenant_id:
        return tenant_id

    if _should_bypass_auth(request):
        return get_default_tenant_id()

    return None

"""
LegiVellum Authentication Utilities

Shared auth utilities for extracting tenant_id from requests.
MVP: Simple API key auth. Production: JWT token validation.
"""
import os
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

# API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Auth token header (for future JWT support)
auth_header = APIKeyHeader(name="Authorization", auto_error=False)


# MVP: Simple API key to tenant_id mapping
# In production, this would be a database lookup or JWT claim extraction
API_KEY_TENANT_MAP = {
    "dev-key-pstryder": "pstryder",
    "dev-key-alice": "alice",
    "dev-key-bob": "bob",
    "test-key": "test",
}


def get_tenant_from_api_key(api_key: str) -> Optional[str]:
    """Map API key to tenant_id"""
    # Check environment variable for additional keys
    env_key = os.environ.get("LEGIVELLUM_API_KEY")
    env_tenant = os.environ.get("LEGIVELLUM_TENANT_ID", "pstryder")

    if env_key and api_key == env_key:
        return env_tenant

    return API_KEY_TENANT_MAP.get(api_key)


def get_tenant_from_bearer(auth_value: str) -> Optional[str]:
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


async def get_current_tenant(
    api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Security(auth_header),
) -> str:
    """
    FastAPI dependency to extract tenant_id from request.

    Checks:
    1. X-API-Key header
    2. Authorization: Bearer <token> header

    Returns tenant_id or raises 401.
    """
    # Try API key first
    if api_key:
        tenant_id = get_tenant_from_api_key(api_key)
        if tenant_id:
            return tenant_id

    # Try Bearer token
    if authorization:
        tenant_id = get_tenant_from_bearer(authorization)
        if tenant_id:
            return tenant_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_tenant(
    api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Security(auth_header),
) -> Optional[str]:
    """
    Optional tenant extraction (for endpoints that support anonymous access).
    Returns None if no valid auth found.
    """
    if api_key:
        tenant_id = get_tenant_from_api_key(api_key)
        if tenant_id:
            return tenant_id

    if authorization:
        tenant_id = get_tenant_from_bearer(authorization)
        if tenant_id:
            return tenant_id

    return None

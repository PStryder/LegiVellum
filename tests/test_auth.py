"""Unit tests for shared auth behavior."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from legivellum.auth import get_current_tenant, get_tenant_from_api_key


@pytest.fixture(autouse=True)
def cleanup_database():
    """Override global DB cleanup fixture for this pure-unit module."""
    yield


def _local_request() -> Request:
    scope = {
        "type": "http",
        "scheme": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(b"host", b"localhost:8080")],
        "client": ("127.0.0.1", 55000),
        "server": ("localhost", 8080),
    }
    return Request(scope)


def test_get_tenant_from_api_key_supports_patterned_keys():
    assert get_tenant_from_api_key("dev-key-alpha") == "alpha"
    assert get_tenant_from_api_key("test-key-tenant_7") == "tenant_7"


def test_get_tenant_from_api_key_supports_env_tenant_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TENANT_API_KEY_nova", "secret-nova-key")
    assert get_tenant_from_api_key("secret-nova-key") == "nova"


@pytest.mark.asyncio
async def test_get_current_tenant_auto_mode_allows_local_bypass(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LEGIVELLUM_AUTH_MODE", "auto")
    monkeypatch.setenv("LEGIVELLUM_DEFAULT_TENANT", "localdev")

    tenant_id = await get_current_tenant(
        api_key=None,
        authorization=None,
        request=_local_request(),
    )

    assert tenant_id == "localdev"


@pytest.mark.asyncio
async def test_get_current_tenant_strict_mode_requires_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LEGIVELLUM_AUTH_MODE", "strict")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant(
            api_key=None,
            authorization=None,
            request=_local_request(),
        )

    assert exc_info.value.status_code == 401

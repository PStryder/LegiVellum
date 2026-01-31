import asyncio
import hashlib
import json
import os
import secrets
from uuid import uuid4

import asyncpg


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


async def main() -> None:
    dsn = _env("METAGATE_DB_DSN", "postgresql://metagate:metagate@metagate-db:5432/metagate")
    tenant_key = _env("PROBLEMATA_TENANT_KEY", "default")
    deployment_key = _env("PROBLEMATA_DEPLOYMENT_KEY", "local")

    principal_key = _env("PROBLEMATA_PRINCIPAL_KEY", "problemata-demo-principal")
    auth_subject = _env("PROBLEMATA_AUTH_SUBJECT", "problemata-demo-subject")
    profile_key = _env("PROBLEMATA_PROFILE_KEY", "problemata-demo-profile")
    manifest_key = _env("PROBLEMATA_MANIFEST_KEY", "problemata-demo-manifest")

    services = {
        "metagate": {"url": _env("METAGATE_URL", "http://metagate:8000"), "auth": "api_key"},
        "receiptgate": {"url": _env("RECEIPTGATE_URL", "http://receiptgate:8000"), "auth": "api_key"},
        "depotgate": {"url": _env("DEPOTGATE_URL", "http://depotgate:8000"), "auth": "api_key"},
        "asyncgate": {"url": _env("ASYNCGATE_URL", "http://asyncgate:8080"), "auth": "api_key"},
    }

    memory_map = {
        "receipts": {"gate": "receiptgate", "namespace": tenant_key},
        "artifacts": {"gate": "depotgate", "namespace": tenant_key},
    }

    polling = {
        "asyncgate": {"endpoint": "/v1/poll", "interval_ms": 1000},
    }

    schemas = {
        "receipt_schema": "receipt.schema.v1.json",
        "manifest_schema": "metagate.manifest.v0.json",
    }

    environment = {
        "stage": "development",
        "region": "local",
        "deployment": deployment_key,
    }

    capabilities = {
        "memory_read": True,
        "memory_write": True,
        "async_poll": True,
    }

    policy = {
        "max_memory_mb": 1024,
        "rate_limit_rps": 100,
    }

    conn = await asyncpg.connect(dsn)
    try:
        print("Seeding MetaGate database for problemata demo...")

        principal_id = uuid4()
        await conn.execute(
            """
            INSERT INTO principals (id, tenant_key, principal_key, auth_subject, principal_type, status)
            VALUES ($1, $2, $3, $4, 'component', 'active')
            ON CONFLICT (principal_key) DO NOTHING
            """,
            principal_id,
            tenant_key,
            principal_key,
            auth_subject,
        )

        profile_id = uuid4()
        await conn.execute(
            """
            INSERT INTO profiles (id, tenant_key, profile_key, capabilities, policy, startup_sla_seconds)
            VALUES ($1, $2, $3, $4, $5, 120)
            ON CONFLICT (profile_key) DO NOTHING
            """,
            profile_id,
            tenant_key,
            profile_key,
            json.dumps(capabilities),
            json.dumps(policy),
        )

        manifest_id = uuid4()
        await conn.execute(
            """
            INSERT INTO manifests (
                id, tenant_key, manifest_key, deployment_key, environment, services,
                memory_map, polling, schemas, version
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 1)
            ON CONFLICT (manifest_key) DO NOTHING
            """,
            manifest_id,
            tenant_key,
            manifest_key,
            deployment_key,
            json.dumps(environment),
            json.dumps(services),
            json.dumps(memory_map),
            json.dumps(polling),
            json.dumps(schemas),
        )

        principal_row = await conn.fetchrow(
            "SELECT id FROM principals WHERE principal_key = $1", principal_key
        )
        profile_row = await conn.fetchrow(
            "SELECT id FROM profiles WHERE profile_key = $1", profile_key
        )
        manifest_row = await conn.fetchrow(
            "SELECT id FROM manifests WHERE manifest_key = $1", manifest_key
        )

        binding_id = uuid4()
        await conn.execute(
            """
            INSERT INTO bindings (id, tenant_key, principal_id, profile_id, manifest_id, active)
            VALUES ($1, $2, $3, $4, $5, true)
            ON CONFLICT DO NOTHING
            """,
            binding_id,
            tenant_key,
            principal_row["id"],
            profile_row["id"],
            manifest_row["id"],
        )

        api_key = f"mgk_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO api_keys (id, tenant_key, key_hash, principal_id, name, status)
            VALUES ($1, $2, $3, $4, 'Problemata Demo Key', 'active')
            ON CONFLICT (key_hash) DO NOTHING
            """,
            uuid4(),
            tenant_key,
            key_hash,
            principal_row["id"],
        )

        print("\n" + "=" * 72)
        print("PROBLEMATA DEMO SEED COMPLETE")
        print("=" * 72)
        print(f"Tenant: {tenant_key}")
        print(f"Deployment: {deployment_key}")
        print(f"Principal Key: {principal_key}")
        print(f"Auth Subject: {auth_subject}")
        print(f"Profile Key: {profile_key}")
        print(f"Manifest Key: {manifest_key}")
        print("\nService URLs:")
        for name, config in services.items():
            print(f"  {name}: {config['url']}")
        print("\nAPI Key (save this - shown only once):")
        print(f"  {api_key}")
        print("\nBootstrap example:")
        print("  curl -X POST http://localhost:8100/v1/bootstrap ")
        print(f"    -H \"X-API-Key: {api_key}\" ")
        print("    -H \"Content-Type: application/json\" ")
        print("    -d '{\"component_key\": \"asyncgate_demo\"}'")
        print("=" * 72)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

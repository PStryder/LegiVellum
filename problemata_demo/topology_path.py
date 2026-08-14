#!/usr/bin/env python3
"""Topology path: author a Problemata, publish it, then bootstrap into it.

This closes the loop the architecture always described but never had:

    control plane  ->  MetaGate  ->  component
    (authors and       (materializes    (bootstraps and
     validates)         world-truth)     receives topology)

Before this, both arrows were missing. The control plane authored specs that
nothing consumed, and MetaGate served config that nothing asked for -- the
demo stack seeded it with raw SQL INSERTs instead.

What this proves, in order:
  1. The control plane compiles and validates a Problemata spec.
  2. MetaGate materializes it as principal + profile + manifest + binding,
     describe-only -- no deploy, provision or execute.
  3. A component bootstrapping against MetaGate receives the topology the
     spec described, with the endpoints it declared.
  4. Re-publishing the same spec is idempotent.
  5. An unvalidated spec is refused.

Usage:
    python topology_path.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# The control plane lives in the LegiVellum package next to this demo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

from legivellum.problemata_control import (  # noqa: E402
    InMemoryProblemataRepository,
    ProblemataBlueprint,
    ProblemataControlService,
    ProblemataStatus,
)
from legivellum.problemata_publish import (  # noqa: E402
    MetaGatePublisher,
    ProblemataPublishError,
)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _mcp(url: str, tool: str, arguments: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    endpoint = url if url.endswith("/mcp") else f"{url.rstrip('/')}/mcp"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    if api_key:
        request.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    if "error" in body:
        raise RuntimeError(f"{tool} failed: {body['error']}")
    return body["result"]


def main() -> int:
    metagate_url = _env("METAGATE_URL", "http://localhost:8100")
    metagate_key = _env("METAGATE_API_KEY")
    # Primitive endpoints are derived from this base as {base}/{type}/mcp.
    endpoint_base = _env("PROBLEMATA_ENDPOINT_BASE", "http://problemata-demo.internal")
    problemata_id = _env("PROBLEMATA_DEMO_ID", "demo-topology")
    owner = _env("PROBLEMATA_OWNER_ID", "principal-topology-demo")
    expected_receiptgate = f"{endpoint_base}/receiptgate/mcp"

    # 1. Author and validate, in the control plane.
    print("1. Authoring Problemata spec in the control plane...")
    service = ProblemataControlService(repository=InMemoryProblemataRepository())
    record = service.create_from_blueprint(
        ProblemataBlueprint(
            problemata_id=problemata_id,
            tenant_id="default",
            owner_principal=owner,
            description="Proves control plane -> MetaGate -> component",
            endpoint_base=endpoint_base,
        )
    )
    if record.status is not ProblemataStatus.VALIDATED:
        raise RuntimeError(f"Spec did not validate: {record.validation}")
    declared = set(record.spec["primitives"])
    print(f"   validated {record.problemata_id} v{record.version}")
    print(f"   declares {len(declared)} primitives: {', '.join(sorted(declared))}")

    # 2. Publish to MetaGate.
    print("\n2. Publishing to MetaGate...")
    publisher = MetaGatePublisher(metagate_url, api_key=metagate_key)
    result = publisher.publish_record(record, deployment_key="local", auth_subject=owner)
    print(f"   principal : {result['principal_key']}")
    print(f"   profile   : {result['profile_key']}")
    print(f"   manifest  : {result['manifest_key']}")
    print(f"   binding   : {result['binding_id']} (created={result['binding_created']})")
    print(f"   capabilities: {', '.join(result['capabilities'])}")

    if set(result["services"]) != declared:
        raise RuntimeError(
            f"MetaGate materialized {result['services']}, spec declared {sorted(declared)}"
        )

    # 3. Bootstrap into it, as a component would.
    # Bootstrap as the owner principal, not the operator: MetaGate resolves the
    # binding from the authenticated identity, so publishing and consuming
    # topology are deliberately different credentials.
    owner_key_env = _env("METAGATE_OWNER_API_KEY")
    if not owner_key_env:
        raise RuntimeError(
            "METAGATE_OWNER_API_KEY is required to bootstrap as the Problemata "
            "owner; run the metagate-seed profile and export the printed value."
        )

    print("\n3. Bootstrapping a component against MetaGate...")
    packet = _mcp(
        metagate_url,
        "metagate.bootstrap",
        {"component_key": "topology-demo-worker"},
        owner_key_env,
    )
    packet = packet.get("packet", packet)
    services = packet.get("services") or {}
    print(f"   manifest received : {packet.get('manifest')}")
    print(f"   services received : {', '.join(sorted(services))}")

    if set(services) != declared:
        raise RuntimeError(
            f"Bootstrap returned {sorted(services)}, spec declared {sorted(declared)}"
        )
    if services.get("receiptgate-main", {}).get("endpoint") != expected_receiptgate:
        raise RuntimeError(
            "Bootstrap did not carry the endpoint the spec declared: "
            f"{services.get('receiptgate-main')} != {expected_receiptgate}"
        )
    topology_edges = (packet.get("environment") or {}).get("topology")
    if topology_edges is not None:
        print(f"   topology edges    : {len(topology_edges)}")

    # 4. Republishing the same spec must not fork the topology.
    print("\n4. Re-publishing the same spec (idempotency)...")
    again = publisher.publish_record(record, deployment_key="local", auth_subject=owner)
    if again["manifest_key"] != result["manifest_key"]:
        raise RuntimeError("Re-publish produced a different manifest")
    if again["binding_created"]:
        raise RuntimeError("Re-publish created a second binding")
    print(f"   same manifest, no new binding: {again['manifest_key']}")

    # 5. An unvalidated spec must be refused.
    print("\n5. Refusing an unvalidated spec...")
    rejected = record.model_copy(update={"status": ProblemataStatus.REJECTED})
    try:
        publisher.publish_record(rejected)
    except ProblemataPublishError as exc:
        print(f"   refused as expected: {exc}")
    else:
        raise RuntimeError("An unvalidated spec was published")

    print("\nTopology path complete: authored, materialized, and bootstrapped into.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - demo script surfaces the reason
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

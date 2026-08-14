#!/usr/bin/env python3
"""Bind a running gate to a published Problemata and prove it boots into it.

topology_path.py proves a Problemata can be authored, materialized, and
bootstrapped into by a client. This proves the last link: a *real gate* takes
its world-truth from MetaGate rather than from environment variables.

The sequence is necessarily this order, because AsyncGate starts before
anything has been seeded:

  1. Publish a Problemata owned by AsyncGate's principal, declaring the
     in-network endpoints this stack actually uses.
  2. Restart AsyncGate so it bootstraps against the now-published topology.
  3. Assert its logs show a successful bootstrap naming that manifest.

AsyncGate keeps ASYNCGATE_RECEIPTGATE_URL configured, so the other demo paths
cannot be broken by a bootstrap regression -- explicit configuration wins by
design. The proof here is that the gate reached MetaGate and resolved the
manifest, not that it had no other way to find ReceiptGate.

Usage:
    python bind_asyncgate_path.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

from legivellum.problemata_control import (  # noqa: E402
    InMemoryProblemataRepository,
    ProblemataBlueprint,
    ProblemataControlService,
    ProblemataStatus,
)
from legivellum.problemata_publish import MetaGatePublisher  # noqa: E402


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _compose(*args: str) -> str:
    result = subprocess.run(
        ["docker", "compose", *args],
        cwd=str(Path(__file__).resolve().parent),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout + result.stderr


def main() -> int:
    metagate_url = _env("METAGATE_URL", "http://localhost:8100")
    operator_key = _env("METAGATE_API_KEY")
    if not operator_key:
        raise RuntimeError(
            "METAGATE_API_KEY (operator, admin) is required; run the metagate-seed profile."
        )
    asyncgate_principal = _env("PROBLEMATA_ASYNCGATE_PRINCIPAL", "principal-asyncgate")
    problemata_id = _env("PROBLEMATA_ASYNCGATE_ID", "demo-asyncgate-mesh")

    # 1. Publish a Problemata owned by AsyncGate's principal. endpoint_base is
    #    the in-network hostname, so the manifest describes the mesh as it
    #    actually is rather than as localhost.
    print("1. Publishing a Problemata owned by AsyncGate's principal...")
    service = ProblemataControlService(repository=InMemoryProblemataRepository())
    record = service.create_from_blueprint(
        ProblemataBlueprint(
            problemata_id=problemata_id,
            tenant_id="default",
            owner_principal=asyncgate_principal,
            description="Describes this stack and binds the running AsyncGate to it",
            include_interview=True,
            # The real in-network addresses of this stack. Per-primitive
            # overrides exist because endpoint_base alone derives
            # {base}/{type}/mcp -- one gateway host with per-type paths --
            # which cannot describe a compose network where every service has
            # its own hostname.
            endpoints={
                "metagate": _env("MESH_METAGATE", "http://metagate:8000/mcp"),
                "receiptgate": _env("MESH_RECEIPTGATE", "http://receiptgate:8000/mcp"),
                "depotgate": _env("MESH_DEPOTGATE", "http://depotgate:8000/mcp"),
                "asyncgate": _env("MESH_ASYNCGATE", "http://asyncgate:8080/mcp"),
                "interview": _env("MESH_INTERVIEW", "http://interview:8000/mcp"),
            },
        )
    )
    if record.status is not ProblemataStatus.VALIDATED:
        raise RuntimeError(f"Spec did not validate: {record.validation}")

    publisher = MetaGatePublisher(metagate_url, api_key=operator_key)
    result = publisher.publish_record(record, deployment_key="local")
    manifest_key = result["manifest_key"]
    print(f"   manifest : {manifest_key}")
    print(f"   bound to : {result['principal_key']}")
    print(f"   services : {', '.join(result['services'])}")

    # The manifest must describe the stack that is actually running, not a
    # placeholder. Assert the addresses the gates really answer on.
    published = {p["type"]: p["endpoint"] for p in record.spec["primitives"].values()}
    for primitive_type, expected in (
        ("receiptgate", "http://receiptgate:8000/mcp"),
        ("asyncgate", "http://asyncgate:8080/mcp"),
        ("metagate", "http://metagate:8000/mcp"),
    ):
        if published.get(primitive_type) != expected:
            raise RuntimeError(
                f"published {primitive_type} endpoint is {published.get(primitive_type)!r}, "
                f"expected the live address {expected!r}"
            )
    print("   endpoints describe the running stack")

    # `docker compose restart` reuses the container, so its log keeps every
    # earlier attempt -- including the failed boot from before anything was
    # seeded. Count the existing markers first and wait for a *new* one, rather
    # than pattern-matching a tail that already contains the old result.
    def _bootstrap_lines() -> list[str]:
        logs = _compose("logs", "--no-color", "asyncgate")
        return [line for line in logs.splitlines() if "metagate_bootstrap" in line]

    before = len(_bootstrap_lines())

    print("\n2. Restarting AsyncGate so it bootstraps into it...")
    _compose("restart", "asyncgate")

    print("\n3. Checking AsyncGate bootstrapped against that manifest...")
    deadline = time.monotonic() + 120
    new_lines: list[str] = []
    while time.monotonic() < deadline:
        lines = _bootstrap_lines()
        if len(lines) > before:
            new_lines = lines[before:]
            # Wait for the attempt to resolve rather than reporting the first
            # line of it.
            if any("metagate_bootstrap_ok" in l or "metagate_bootstrap_failed" in l for l in new_lines):
                break
        time.sleep(3)

    for line in new_lines:
        print(f"   {line.split('|', 1)[-1].strip()}")

    if not new_lines:
        raise RuntimeError("AsyncGate logged no bootstrap attempt after restart")
    if not any("metagate_bootstrap_ok" in line for line in new_lines):
        raise RuntimeError("AsyncGate did not report a successful MetaGate bootstrap")
    if not any(manifest_key in line for line in new_lines):
        raise RuntimeError(f"AsyncGate bootstrapped, but not against {manifest_key}")

    print("\nBind path complete: a running gate took its world-truth from a published Problemata.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - demo script surfaces the reason
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

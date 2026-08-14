#!/usr/bin/env python3
"""Block until every demo-stack service answers its MCP health tool.

The compose stack has healthchecks on the databases and MetaGate, but
ReceiptGate and DepotGate have none, and ReceiptGate pip-installs itself on
container start. `docker compose up -d` therefore returns well before the
stack can serve traffic. The demo scripts' own wait_for() allows 30s, which is
not enough from a cold CI runner with no image cache.

Usage:
    python wait_for_stack.py [--timeout SECONDS]

Exits 0 when all services are healthy, 1 on timeout (naming what never came
up, so a CI failure is readable without digging through container logs).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# service name -> (base url env var, default url)
SERVICES: dict[str, tuple[str, str]] = {
    "metagate": ("METAGATE_URL", "http://localhost:8100"),
    "depotgate": ("DEPOTGATE_URL", "http://localhost:8200"),
    "receiptgate": ("RECEIPTGATE_URL", "http://localhost:8300"),
    "asyncgate": ("ASYNCGATE_URL", "http://localhost:8400"),
}


def _health_once(service: str, base_url: str, timeout: float = 5.0) -> bool:
    """Return True if `<service>.health` responds with an MCP result."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": f"{service}.health", "arguments": {}},
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/mcp",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    api_key = os.environ.get(f"{service.upper()}_API_KEY")
    if api_key:
        request.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return False
    return "result" in body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=300.0, help="seconds to wait")
    parser.add_argument("--interval", type=float, default=3.0, help="seconds between polls")
    args = parser.parse_args()

    pending = dict(SERVICES)
    started = time.monotonic()
    deadline = started + args.timeout

    while pending and time.monotonic() < deadline:
        for service in list(pending):
            env_var, default_url = pending[service]
            base_url = os.environ.get(env_var) or default_url
            if _health_once(service, base_url):
                elapsed = time.monotonic() - started
                print(f"  healthy: {service} ({base_url}) after {elapsed:.0f}s", flush=True)
                del pending[service]
        if pending:
            time.sleep(args.interval)

    if pending:
        elapsed = time.monotonic() - started
        print(f"\nTimed out after {elapsed:.0f}s. Never became healthy:", flush=True)
        for service, (env_var, default_url) in pending.items():
            print(f"  - {service} ({os.environ.get(env_var) or default_url})", flush=True)
        return 1

    print("\nAll demo-stack services healthy.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Plan path: intent becomes cognition becomes obligations becomes work.

The golden path starts with a task that already exists. This one starts with a
sentence, and follows it all the way down:

    intent
      -> DeleGate plans it (cognitively, via its configured provider)
      -> plan receipt: accepted -> complete, plan in the body
      -> DeleGate mints one AsyncGate obligation per executable step,
         each naming the plan receipt as its cause
      -> CogniGate leases those obligations and executes them
      -> receipts close the chain

CogniGate is registered with DeleGate as the worker, so the plan targets a real
executor rather than a hypothetical one. That is also what makes this runnable
in CI: both DeleGate and CogniGate default to stub providers, so the whole
chain runs with no model and no API key.

What this proves that the other paths do not: that a plan is not a document.
DeleGate is one of only two things permitted to mint obligations, and this is
the path where it does.

Usage:
    python plan_path.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


DELEGATE_URL = _env("DELEGATE_URL", "http://localhost:8700")
ASYNCGATE_URL = _env("ASYNCGATE_URL", "http://localhost:8400")
RECEIPTGATE_URL = _env("RECEIPTGATE_URL", "http://localhost:8300")
ASYNCGATE_API_KEY = _env("ASYNCGATE_API_KEY", "dev_asyncgate_key")
TENANT_ID = _env("PROBLEMATA_ASYNCGATE_TENANT", "00000000-0000-0000-0000-000000000000")
# Must match COGNIGATE_WORKER_ID so DeleGate plans against the worker that will
# actually lease the obligations.
COGNIGATE_URL = _env("COGNIGATE_URL", "http://localhost:8500")
COGNIGATE_WORKER_ID = _env("COGNIGATE_WORKER_ID", "cognigate-demo-1")
INTENT = _env("PLAN_INTENT", "research competitors and draft a summary report")


def _mcp(base_url: str, tool: str, arguments: dict[str, Any], api_key: str | None = None) -> dict[str, Any]:
    endpoint = base_url if base_url.endswith("/mcp") else f"{base_url.rstrip('/')}/mcp"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": tool, "arguments": arguments}}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.load(response)
    if "error" in body:
        raise RuntimeError(f"{tool} failed: {body['error']}")
    result = body.get("result")
    if result is None:
        raise RuntimeError(f"{tool} returned no result")
    return result


def register_cognigate_as_worker() -> None:
    """Register the running CogniGate in DeleGate's worker registry.

    DeleGate refuses to plan work no registered worker can do, which is correct
    -- a plan targeting a capability nobody has is a plan that cannot execute.
    """
    print("1. Registering CogniGate as a DeleGate worker...")
    result = _mcp(
        DELEGATE_URL,
        "delegate.register_worker",
        {
            "worker_id": COGNIGATE_WORKER_ID,
            "worker_name": "CogniGate (bounded cognition)",
            # Numeric tier: 3 == trusted in DeleGate's TrustTier enum.
            "trust": {"declared_tier": 3},
            "capabilities": [
                {
                    "tool_name": "text.summarize",
                    "description": "Summarise and analyse text under lease",
                    "semantic_tags": ["summarize", "report", "research", "analyse", "draft"],
                },
                {
                    "tool_name": "general",
                    "description": "General bounded cognitive work",
                    "semantic_tags": ["general", "execute"],
                },
            ],
        },
    )
    print(f"   registered {result['worker_id']} "
          f"({result['capabilities_registered']} capabilities, {result['trust_tier']})")
    start_cognigate_polling()


def start_cognigate_polling() -> None:
    """Tell CogniGate to start leasing.

    Its poller is constructed at startup but only started on demand, so a
    freshly started CogniGate holds no leases until asked. That is deliberate
    -- a cognitive worker should not begin consuming obligations merely because
    its process exists -- but it does mean the demo has to say go.
    """
    result = _mcp(COGNIGATE_URL, "cognigate.polling_start", {})
    print(f"   polling: {result.get('status', result)}")


def create_plan() -> dict[str, Any]:
    print(f"\n2. Planning: {INTENT!r}")
    response = _mcp(DELEGATE_URL, "delegate.create_delegation_plan", {"intent": INTENT})

    if response.get("status") != "plan_created":
        raise RuntimeError(
            f"Expected plan_created, got {response.get('status')}: "
            f"{response.get('message') or response.get('reason')}"
        )

    plan = response["plan"]
    metadata = plan["metadata"]
    print(f"   plan       : {metadata['plan_id']}")
    print(f"   scope      : {metadata['scope']} (confidence {metadata['confidence']})")
    print(f"   steps      : {len(plan['steps'])}")
    return response


def check_dispatch(response: dict[str, Any]) -> list[dict[str, Any]]:
    """A plan that mints nothing is a document."""
    dispatch = response.get("dispatch")
    if not dispatch:
        raise RuntimeError("Plan produced no dispatch: nothing was minted downstream")

    print(f"\n3. Obligations minted in AsyncGate: {dispatch['dispatched_count']} "
          f"({dispatch['failed_count']} failed)")
    for task in dispatch["tasks"]:
        print(f"   step {task['step_number']}: {task['task_id']}  {task['description']}")
    for failure in dispatch["failures"]:
        print(f"   step {failure['step_number']} FAILED: {failure['error']}")

    if dispatch["failed_count"]:
        raise RuntimeError("Some plan steps were not minted")
    if not dispatch["tasks"]:
        raise RuntimeError("Plan minted no obligations")
    return dispatch["tasks"]


def check_provenance(tasks: list[dict[str, Any]], plan_id: str) -> None:
    """Every obligation must name the plan receipt that caused it.

    This is what makes "why does this work exist?" answerable by traversal
    rather than inference.
    """
    print("\n4. Checking provenance on each obligation...")
    causes = set()
    for task in tasks:
        detail = _mcp(
            ASYNCGATE_URL,
            "asyncgate.get_task",
            {"task_id": task["task_id"], "tenant_id": TENANT_ID},
            ASYNCGATE_API_KEY,
        )
        payload = detail.get("payload") or {}
        cause = payload.get("caused_by_receipt_id")
        if not cause or cause == "NA":
            raise RuntimeError(f"Task {task['task_id']} names no causing receipt")
        if payload.get("plan_id") != plan_id:
            raise RuntimeError(
                f"Task {task['task_id']} claims plan {payload.get('plan_id')}, expected {plan_id}"
            )
        causes.add(cause)
        print(f"   {task['task_id'][:8]}...  caused_by {cause}  "
              f"(step {payload.get('step_number')} of {payload.get('step_count')})")

    if len(causes) != 1:
        raise RuntimeError(f"Steps of one plan cite different causes: {causes}")


def await_execution(tasks: list[dict[str, Any]], timeout_seconds: float = 120.0) -> int:
    """Wait for CogniGate to lease and finish the minted obligations.

    Polls rather than sleeping blindly: CogniGate's polling interval and the
    stub's speed both vary, and a fixed sleep is either slow or flaky.
    """
    print("\n5. Waiting for CogniGate to lease and execute them...")
    terminal = {"succeeded", "failed", "canceled", "completed"}
    deadline = time.monotonic() + timeout_seconds
    finished: dict[str, str] = {}

    while time.monotonic() < deadline and len(finished) < len(tasks):
        for task in tasks:
            if task["task_id"] in finished:
                continue
            detail = _mcp(
                ASYNCGATE_URL,
                "asyncgate.get_task",
                {"task_id": task["task_id"], "tenant_id": TENANT_ID},
                ASYNCGATE_API_KEY,
            )
            status = str(detail.get("status") or "").lower()
            if status in terminal:
                finished[task["task_id"]] = status
                print(f"   {task['task_id'][:8]}...  {status}")
        if len(finished) < len(tasks):
            time.sleep(3)

    if not finished:
        print("   (none reached a terminal state within the timeout)")
    return len(finished)


def main() -> int:
    register_cognigate_as_worker()
    response = create_plan()
    plan_id = response["plan"]["metadata"]["plan_id"]
    tasks = check_dispatch(response)
    check_provenance(tasks, plan_id)

    executed = await_execution(tasks)

    print("\nPlan path complete: an intent became a cognitive plan, the plan "
          "minted obligations, and each obligation names the plan receipt that "
          "caused it.")
    if executed < len(tasks):
        # Not fatal: minting is DeleGate's responsibility and it succeeded.
        # Execution is the worker's, and is reported rather than asserted so a
        # slow worker does not fail the planning claim.
        print(f"note: {executed}/{len(tasks)} obligations reached a terminal "
              "state before the timeout; the rest remain open in AsyncGate.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - demo script surfaces the reason
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

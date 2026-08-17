"""The demo stack's tenant wiring has to agree with itself.

A receipt claiming a tenant its emitter is not scoped to is refused
(`TENANT_MISMATCH`, `legivellum.authority.bind_identity`). In the demo stack
AsyncGate stamped receipts with its own tenant UUID while ReceiptGate's
principal sat at the library default `"default"`, so *every* receipt the golden
path produced was rejected -- and AsyncGate's circuit breaker buffered them and
returned success to the caller. The demo reported a completed task with an
empty ledger.

Nothing failed loudly, which is the point: this is the exact shape Slice Zero
exists to eliminate, reached through configuration rather than code. So the
wiring is asserted here, where a mismatch is a test failure rather than a
buffered receipt.

These read the compose file as data. They do not need the stack running.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

COMPOSE = (
    Path(__file__).resolve().parents[1] / "problemata_demo" / "docker-compose.yml"
)

# The tenant every gate in the demo agrees an obligation belongs to. Written out
# rather than read from one service, so a change to that service is a failure
# here instead of a silently-agreed new value.
DEMO_TENANT = "00000000-0000-0000-0000-000000000000"

# `${VAR:-default}` -- what compose resolves to with no .env present, which is
# how the demo is documented to run.
_INTERPOLATION = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*:-(?P<default>.*)\}$")


def _resolved(value: object) -> str:
    text = str(value)
    match = _INTERPOLATION.match(text)
    return match.group("default") if match else text


@pytest.fixture(scope="module")
def services() -> dict:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return compose["services"]


def _env(services: dict, service: str) -> dict[str, str]:
    environment = services[service].get("environment") or {}
    if isinstance(environment, list):  # compose also allows KEY=value strings
        environment = dict(item.split("=", 1) for item in environment)
    return {key: _resolved(value) for key, value in environment.items()}


@pytest.mark.parametrize(
    ("service", "variable"),
    [
        ("receiptgate", "RECEIPTGATE_DEFAULT_TENANT_ID"),
        ("metagate", "METAGATE_DEFAULT_TENANT_KEY"),
        ("delegate", "DELEGATE_DEFAULT_TENANT_ID"),
        ("delegate", "DELEGATE_ASYNCGATE_TENANT_ID"),
        ("cognigate", "COGNIGATE_ASYNCGATE_TENANT_ID"),
    ],
)
def test_every_tenant_knob_resolves_to_one_tenant(services, service, variable):
    """One ledger, one principal, therefore one tenant.

    MetaGate names tenants with string keys and AsyncGate with UUIDs, and both
    namespaces feed the same ledger under the same principal. While they
    disagreed, whichever emitter did not match was refused TENANT_MISMATCH on
    every receipt: MetaGate-side components stamped "default", AsyncGate-side
    components stamped the UUID, and only one of them could ever commit.

    Asserted per knob rather than "all equal to each other" so a failure names
    the setting that drifted.
    """
    environment = _env(services, service)
    assert variable in environment, (
        f"{service} does not set {variable}, so it falls back to its own "
        f"library default and emits into a tenant the ledger will refuse."
    )
    assert environment[variable] == DEMO_TENANT


def test_receiptgate_principal_is_scoped_to_the_obligation_tenant(services):
    """The ledger must accept the tenant its emitters actually write.

    Remove RECEIPTGATE_DEFAULT_TENANT_ID from the compose file and this fails:
    the ledger falls back to "default" and refuses every receipt in the demo.
    """
    receiptgate = _env(services, "receiptgate")

    assert "RECEIPTGATE_DEFAULT_TENANT_ID" in receiptgate, (
        "ReceiptGate has no tenant configured, so its principal falls back to "
        "the library default 'default'. Every receipt the demo emits claims "
        f"tenant {DEMO_TENANT} and is refused TENANT_MISMATCH."
    )
    assert receiptgate["RECEIPTGATE_DEFAULT_TENANT_ID"] == DEMO_TENANT


@pytest.mark.parametrize(
    ("service", "variable"),
    [
        ("delegate", "DELEGATE_ASYNCGATE_TENANT_ID"),
        ("cognigate", "COGNIGATE_ASYNCGATE_TENANT_ID"),
    ],
)
def test_task_creators_use_the_same_tenant(services, service, variable):
    """Whoever creates the task decides the tenant the receipts will carry."""
    assert _env(services, service)[variable] == DEMO_TENANT


def test_no_service_configures_a_separate_receipt_tenant(services):
    """Receipt tenancy is not independently configurable, so nothing may set it.

    `ASYNCGATE_RECEIPTGATE_TENANT_ID` was set here to a value that disagreed
    with the receipts, and read by nothing -- it described a translation between
    tenant namespaces that does not exist. A setting that looks like it controls
    tenancy and does not is worse than no setting: it makes the mismatch look
    handled.
    """
    offenders = {
        f"{service}.{key}"
        for service in services
        for key in _env(services, service)
        if key.endswith("RECEIPTGATE_TENANT_ID")
    }
    assert not offenders, (
        f"{sorted(offenders)} suggest receipt tenancy can be set per emitter. "
        "It cannot: a receipt carries the obligation's tenant, and the ledger "
        "refuses any other."
    )


def test_asyncgate_has_no_receipt_tenant_setting():
    """The dead setting stays dead.

    Reintroducing `receiptgate_tenant_id` would make the compose variable above
    load cleanly again while still changing nothing about what is emitted.
    """
    config = (
        Path(__file__).resolve().parents[2]
        / "AsyncGate"
        / "src"
        / "asyncgate"
        / "config.py"
    )
    if not config.exists():  # AsyncGate is a sibling checkout, not a dependency
        pytest.skip("AsyncGate checkout not present")

    declarations = [
        line
        for line in config.read_text(encoding="utf-8").splitlines()
        if re.match(r"\s*receiptgate_tenant_id\s*[:=]", line)
    ]
    assert not declarations, (
        "asyncgate.config declares receiptgate_tenant_id again. Receipts carry "
        "the obligation's tenant; a setting that claims otherwise is read by "
        "nothing and hides the mismatch it appears to resolve."
    )

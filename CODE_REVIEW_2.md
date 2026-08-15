<!-- Generated 2026-08-15. Stack-level context: ../LV_STACK_REVIEW.md -->

> **Review 2 — LegiVellum**
> Part of a full-stack review of LV_Stack (11 repos, ~97k LOC) conducted 2026-08-15.
> Stack-wide findings that affect this repo but are not fixable inside it are in
> `../LV_STACK_REVIEW.md` and `../_CROSS_REPO_ANALYSIS.md`. Read the stack report first —
> several findings below have a shared root cause.

---

# LegiVellum — Code Review

Reviewer pass: 2026-08-15. Scope: `/home/claude/lv/LegiVellum/` (~30k LOC incl. `.standalone_code/`).

## Verdict

The substrate repo does not hold up its own specs. `shared/legivellum/auth.py` grants any caller
who sends `X-API-Key: dev-key-<anything>` the tenant `<anything>`, in every auth mode including
`strict` — and `tests/test_auth.py:33` asserts that behaviour as a feature. `shared/legivellum/validation.py`
looks for the canonical JSON Schema at `spec/receipt.schema.v1.json`, a directory the repo's own
`CODE_REVIEW.md` says was renamed to `docs/canonical/` — so `validate_json_schema()` returns `[]`
unconditionally and `receipt.rules.md` §9 ("all receipts MUST validate against the schema before
insertion") is enforced nowhere in the shared library. ReceiptGate found and fixed exactly this bug
in its own copy; the shared copy every other gate would import still fails open. On top of that,
`models.py` accepts eleven concrete receipt shapes the canonical schema rejects, `docs/canonical/`
contains three mutually incompatible receipt storage models, and 47 of 118 tests are
`pass  # Placeholder` bodies that report green.

---

## Exit Criteria Scorecard

Per the task brief: this repo ships no service, so several sections are scored N/A with cause.
`problemata_demo/` and `tools/problemata_control_ui/` are the only runnable surfaces.

| # | Section | Score | Notes |
|---|---------|-------|-------|
| 1 | Build & Run | **FAIL** | No `make dev`/`run_local.sh`. Two conflicting `pyproject.toml` files both named `legivellum` with different build backends and incompatible ULID deps (H7). Non-editable install breaks migrations + UI asset mount (H6). `problemata_demo` does build and run under `stack.yml`, which is genuinely good. |
| 2 | API & Contract Stability | **PARTIAL** | `receipt.schema.v1.json` is versioned and stable. But `docs/canonical/ReceiptGate/schema/001_receipts.sql` admits a fourth phase `cancel` that `LegiVellum Integration Lock Spec v0.txt` §2.1 forbids (H9). Problemata control-plane HTTP API is unversioned. |
| 3 | Canonical Principals | **FAIL** | Not N/A — the Exit Criteria template tells nine repos to define `SYSTEM_PRINCIPAL_ID = "sys:legivellum"` / `SERVICE_PRINCIPAL_ID`. The substrate that could define them once defines them zero times (H12). |
| 4 | Receipt Model Invariants | **FAIL** | Not N/A — this repo owns the receipt model. `TERMINAL_RECEIPT_TYPES` appears nowhere in `shared/`, `docs/canonical/`, or `schema/`. Phase constraints diverge from the schema in three layers (H4, H11). |
| 5 | Persistence & Migration | **PARTIAL** | `schema/migrations/problemata_control/` has checksum-verified migrations — good. `schema/receipts.sql` is a dead fourth receipt model no live service uses (H9). No immutability enforcement (H11). |
| 6 | Core Behavioral Guarantees | **PASS** | N/A for a golden path of its own, but `problemata_demo/` provides golden/escalation/observe/topology/plan/bind paths plus an adversarial `invariant_probe.py`, all gated in `stack.yml`. This is the strongest thing in the repo. |
| 7 | Test Requirements | **FAIL** | 47/118 tests are empty placeholders (H10). Zero tests for `validate_json_schema` — which is why C2 survived. No conformance suite for the canonical schema; `examples/receipts/invalid/` is never asserted to be rejected (M2). |
| 8 | Observability | **N/A (mostly)** | Ships no service, so no correlation-key logging to score. The optional `observability/` helper works but latches `ENABLED` at import (L4). |
| 9 | v1 Lock Rules | **FAIL** | Receipt types and terminal semantics are not frozen — they are contradictory across three files in `docs/canonical/` (H9). DB schema has no migration plan for `schema/receipts.sql`. |

---

## Shared Library Findings (highest blast radius)

`shared/legivellum/` is loaded by nine services. Four of the eight demo services mount it
(`../../LegiVellum/shared:/LegiVellum/shared:ro` — `delegate`, `interrogate`, `asyncgate`,
`cognigate`); the rest load `metagate_bootstrap.py` by walking parent directories for
`LegiVellum/shared/legivellum/metagate_bootstrap.py`. There is no version pin and no consumer
contract test, so a signature change here is a silent runtime warning in nine repos, not a build
failure.

### CRITICAL-1 — Any `dev-key-*` / `test-key-*` string authenticates as an arbitrary tenant, in strict mode

`shared/legivellum/auth.py:78-85`

```python
def _tenant_from_key_pattern(api_key: str) -> Optional[str]:
    """Allow dynamic test/dev key formats without static registration."""
    for prefix in ("dev-key-", "test-key-"):
        if api_key.startswith(prefix):
            tenant_id = api_key[len(prefix):].strip()
            if tenant_id:
                return tenant_id
    return None
```

Called from `get_tenant_from_api_key` (line 107) → `_resolve_tenant_from_headers` (line 136) →
`get_current_tenant` (line 190). Note the ordering in `get_current_tenant`:

```python
tenant_id = _resolve_tenant_from_headers(api_key=api_key, authorization=authorization)
if tenant_id:
    return tenant_id
if _should_bypass_auth(request):     # <- mode check happens AFTER
```

The mode check is only reached when header resolution fails. `_tenant_from_key_pattern` is never
gated by `get_auth_mode()`. `get_tenant_from_bearer` (line 114) routes `Authorization: Bearer
dev-key-x` through the same function, so both headers work.

**Failure scenario:** `LEGIVELLUM_AUTH_MODE=strict`, service on the public internet.
`curl -H 'X-API-Key: dev-key-acme' https://host/api/problemata` returns tenant `acme`'s data.
`dev-key-victim` returns the victim tenant's. No credential is required, no key is registered,
no log line distinguishes it from a legitimate request. `receipt.rules.md` §3.2 states "Clients
MUST NOT be able to override or spoof `tenant_id`"; this makes tenant_id fully caller-controlled.

`tests/test_auth.py:32-34` asserts this:

```python
def test_get_tenant_from_api_key_supports_patterned_keys():
    assert get_tenant_from_api_key("dev-key-alpha") == "alpha"
```

There is no test asserting that strict mode rejects an unregistered `dev-key-*`. The bypass is
locked in by the suite.

### CRITICAL-2 — Canonical JSON Schema validation is silently disabled everywhere

`shared/legivellum/validation.py:209-219`

```python
        module_dir = Path(__file__).parent
        schema_path = module_dir.parent.parent / "spec" / "receipt.schema.v1.json"

        # Try alternate path if not found
        if not schema_path.exists():
            schema_path = Path.cwd() / "spec" / "receipt.schema.v1.json"

        if not schema_path.exists():
            # Schema file not found - warn but don't fail
            return []
```

`ls spec` → `No such file or directory`. The schema is at `docs/canonical/receipt.schema.v1.json`.
`CODE_REVIEW.md:5-6` documents the rename: *"the `spec/` directory moved to `docs/canonical/`"* —
the callers were never updated. `validate_json_schema()` therefore returns `[]` for every input,
and `validate_receipt(data)` (line 192-193) performs no schema validation despite `validate_schema`
defaulting to `True`.

`receipt.rules.md:236-237`:
> - All receipts MUST validate against `docs/canonical/receipt.schema.v1.json`
> - Schema validation MUST be performed before database insertion

**Failure scenario:** a gate calls `validate_receipt(payload)`, gets `[]`, and stores a receipt
with `phase="accepted"`, `artifact_size_bytes=9999`, `outcome_text="done"` — all forbidden by the
schema's `accepted` branch. Nothing rejects it at any layer (see H4 and H11; Pydantic and the
SQL CHECKs miss the same fields).

**This exact bug was found and fixed in ReceiptGate.** `ReceiptGate/src/receiptgate/validation_v1.py:88-95`
now raises rather than failing open, and `ReceiptGate/tests/test_validation.py:1-8` documents it:
*"validate_json_schema returned [] on a missing file. Every phase rule in receipt.rules.md was
therefore unenforced in deployment while passing in a source checkout."* The fix was never carried
back to the shared library it was copied from.

Compounding: `validate_receipt_create()` at line 252 passes `validate_schema=False` explicitly, so
even a fixed path would not cover the one function that actually constructs a `Receipt`.

### HIGH-1 — `Host` header is trusted to prove localhost; AUTO is the default mode

`shared/legivellum/auth.py:148-172`

```python
    host_header = request.headers.get("host")
    if host_header:
        hosts.append(host_header.split(":")[0])
    ...
    return any(host.strip().lower() in LOCALHOST_HOSTS for host in hosts if host)

def _should_bypass_auth(request) -> bool:
    mode = get_auth_mode()
    ...
    if mode == AUTH_MODE_AUTO and _is_local_request(request):
        return True
```

`get_auth_mode()` defaults to `AUTH_MODE_AUTO` (line 50). `_is_local_request` returns True if *any*
of {client IP, Host header, URL hostname} is localhost — the Host header is attacker-controlled.

**Failure scenario:** service deployed with no `LEGIVELLUM_AUTH_MODE` set. Attacker at 203.0.113.9:
`curl -H 'Host: localhost' https://host/api/problemata` → `_is_local_request` sees `localhost` in
`hosts`, returns True, `get_current_tenant` returns `get_default_tenant_id()` = `"pstryder"`.
Full unauthenticated access to the default tenant.

### HIGH-2 — Hardcoded API keys in library source, honoured unconditionally

`shared/legivellum/auth.py:24-29`

```python
API_KEY_TENANT_MAP = {
    "dev-key-pstryder": "pstryder",
    "dev-key-alice": "alice",
    "dev-key-bob": "bob",
    "test-key": "test",
}
```

Checked at line 103 with no environment gate. These are permanent credentials compiled into the
library every gate imports. Comparison at line 100 (`normalized_key == env_key`) is also non-constant-time;
minor next to the wildcard, but there is no `secrets.compare_digest` anywhere in the file.

### HIGH-3 — Unknown auth mode fails open; production guide never mentions the variable

`shared/legivellum/auth.py:48-51`

```python
    raw_mode = os.environ.get("LEGIVELLUM_AUTH_MODE", AUTH_MODE_AUTO).strip().lower()
    return AUTH_MODE_ALIASES.get(raw_mode, AUTH_MODE_AUTO)
```

`LEGIVELLUM_AUTH_MODE=production`, `=enforced`, `=STRICT_MODE` — every typo resolves to AUTO, the
bypass mode. A fail-closed default would be `AUTH_MODE_STRICT`. `DEPLOYMENT.md:215` documents only
`LEGIVELLUM_API_KEY`; `LEGIVELLUM_AUTH_MODE` appears nowhere in the deployment guide, so an operator
following it ships with the local bypass live.

### HIGH-4 — `models.py` accepts eleven receipt shapes the canonical schema rejects

`shared/legivellum/models.py:151-172` checks nine fields for `phase=accepted`. The schema's
`accepted` branch (`receipt.schema.v1.json:343-386`) constrains twelve. Missing: `outcome_text`,
`artifact_checksum`, `artifact_size_bytes`. Separately, no field in the model carries a
`min_length=1` constraint, while eighteen schema properties declare `"minLength": 1`.

Demonstrated (jsonschema 4.26, pydantic 2.13, model loaded directly, canonical schema):

```
CASE A accepted+dirty outcome/checksum/size: pydantic ACCEPTED; schema errors = 3
     outcome_text: 'NA' was expected
     artifact_checksum: 'NA' was expected
     artifact_size_bytes: 0 was expected
CASE B empty strings: pydantic ACCEPTED; schema errors = 8
     task_id: '' should be non-empty
     from_principal: '' should be non-empty
     for_principal: '' should be non-empty
     source_system: '' should be non-empty
     recipient_ai: '' should be non-empty
     trust_domain: '' should be non-empty
     task_type: '' should be non-empty
     task_body: '' should be non-empty
```

**Failure scenario:** `Receipt(task_id="", from_principal="", recipient_ai="", phase="accepted", ...)`
constructs successfully and is stored. `recipient_ai=""` is the inbox routing key — the receipt is
addressed to nobody and `receipt.rules.md` §7's inbox query will never return it, so the obligation
is invisible and never resolved. Combined with C2, nothing between the model and the disk catches it.

Field coverage is otherwise correct: model key set and schema property set are identical (verified,
no extra/missing fields), and `extra="forbid"` matches `additionalProperties: false`.

### HIGH-5 — Problemata control plane authenticates a tenant and then throws it away

`shared/legivellum/problemata_control_ui.py:160-165` (representative; all nine routes identical)

```python
    @app.get("/api/problemata", response_model=list[ProblemataRecord])
    async def list_problemata(
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> list[ProblemataRecord]:
        return await _resolve_maybe_await(control_service.list())
```

The leading underscore is the tell — the tenant is resolved and discarded. `AsyncProblemataControlService.list()`
(`problemata_control.py:292`) and `.get()` (line 289) take no tenant. `PostgresProblemataRepository.list()`
(line 427) is `SELECT ... FROM problemata_registry ORDER BY created_at` with no `WHERE` and no `LIMIT`.
`upsert` (line 342) is `ON CONFLICT (problemata_id) DO UPDATE SET ... spec = EXCLUDED.spec` keyed on
`problemata_id` alone.

**Failure scenario:** tenant `alice` authenticates and `PUT /api/problemata/bobs-mesh` with a spec whose
`receiptgate` endpoint points at a host she controls. The upsert overwrites Bob's record. Once that
Problemata is published to MetaGate (`problemata_publish.py:115`), every one of Bob's gates bootstraps
its `receiptgate_endpoint` from it (`metagate_bootstrap.py:187-194`) and ships its receipt stream to
Alice. `receipt.rules.md` §3.1 requires tenant isolation at the database level; the control plane has none.

### HIGH-6 — `parents[2]` path resolution breaks on any non-editable install

`shared/legivellum/problemata_control.py:455-458`

```python
def resolve_problemata_migrations_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "schema" / "migrations" / "problemata_control"
```

`shared/legivellum/problemata_control_ui.py:46-48` does the same for `tools/problemata_control_ui`.
In a checkout, `parents[2]` = repo root. Installed to site-packages, `parents[2]` = `/usr/lib/python3.11`
(verified). Neither `pyproject.toml` declares package data, so `schema/` and `tools/` are not shipped in
the wheel — the path is wrong *and* the target does not exist.

**Failure scenario:** `pip install legivellum` (not `-e`), `PROBLEMATA_AUTO_MIGRATE` unset (defaults
`"true"`, line 538). `PostgresProblemataRepository.startup()` → `apply_problemata_migrations` →
`raise FileNotFoundError(f"Problemata migrations directory not found: /usr/lib/python3.11/schema/...")`.
The control UI dies at first request. Separately `create_app()` calls
`app.mount("/assets", StaticFiles(directory=assets_dir))` (line 87) which raises `RuntimeError` on a
missing directory.

This is precisely the failure class `.github/workflows/stack.yml:8-11` was written to catch —
*"ReceiptGate resolving its schema outside the package"* — and it is still live in two places in the
shared library. The docstring at `problemata_control_ui.py:184-196` shows the team hit the symptom and
fixed the timing (lazy app construction) rather than the path.

### HIGH-7 — Two `pyproject.toml` files claim the same package with incompatible ULID dependencies

Root `pyproject.toml:5-17`: setuptools, `name = "legivellum"`, `"ulid-py>=1.1.0"`.
`shared/pyproject.toml:5-23`: hatchling, `name = "legivellum"`, `"python-ulid>=2.0.0"`, plus
`prometheus-client` / `prometheus-fastapi-instrumentator` that the root omits.

`shared/legivellum/models.py:11,51`:

```python
import ulid
...
    return str(ulid.new())
```

`ulid.new()` is the `ulid-py` API. `python-ulid` exposes `ULID()` and has no module-level `new()`.

**Failure scenario:** anyone installing from `shared/` (the directory `hatch`/`uv` would treat as the
package root, and the one whose metadata lists the observability deps the code actually imports) gets
`python-ulid`. The first call to `generate_receipt_id()` raises `AttributeError: module 'ulid' has no
attribute 'new'` — i.e. no receipt can be minted. Which file is authoritative is undocumented.

### MEDIUM-1 — Lazy repository startup races under concurrency

`shared/legivellum/problemata_control.py:338-341`

```python
    async def _ensure_ready(self) -> None:
        if self._session_factory is None:
            await self.startup()
```

No lock, and `startup()` awaits (`apply_problemata_migrations`, line 329). Two concurrent first
requests both observe `None`, both call `startup()`, both call `create_engine` — one engine is leaked
with `_owns_engine` bookkeeping (line 316) that no longer describes reality, so `shutdown()` disposes
one of two. Both also run migrations concurrently: the `INSERT INTO legivellum_schema_migrations`
(line 522) is a PK insert on `(component, version)`, so the loser gets `UniqueViolation` and the
request 500s. `InMemoryProblemataRepository` uses `threading.RLock` (line 168) but the Postgres path
has no equivalent.

### MEDIUM-2 — `close_database()` leaves a session factory bound to a disposed engine

`shared/legivellum/database.py:62-66`

```python
async def close_database():
    global _engine
    if _engine:
        await _engine.dispose()
```

`_session_factory` is not reset, and `_engine` is not set to `None`. After shutdown, `get_session()`
(line 72) still passes its `_session_factory is None` guard and hands out sessions on a disposed
engine. **Failure scenario:** a FastAPI lifespan calls `close_database()` on shutdown; a request still
in flight gets `InvalidRequestError`/connection-closed instead of a clean 503.

### MEDIUM-3 — Personal handle is the default tenant in three places

`shared/legivellum/models.py:68` `tenant_id: str = Field(default="pstryder", ...)`;
`auth.py:56` and `auth.py:99` both default to `"pstryder"`; `schema/receipts.sql:19`
`tenant_id TEXT NOT NULL DEFAULT 'pstryder'`. Any `Receipt(...)` constructed without an explicit
tenant lands in one operator's namespace rather than failing. `receipt.schema.v1.json:59` suggests
`'default'`.

### LOW — `metagate_bootstrap.py` timeout can be `None`

`shared/legivellum/metagate_bootstrap.py:168` uses `getattr(settings, "...", DEFAULT_TIMEOUT_SECONDS)`,
which returns `None` if the attribute exists and is `None`; `httpx.AsyncClient(timeout=None)` waits
forever, contradicting the module's own "bootstrap must never prevent startup" contract. Verified all
eight current consumers declare `float = 5.0`, so this is latent, not live. Use
`getattr(...) or DEFAULT_TIMEOUT_SECONDS`. Otherwise this module is the best code in the repo:
explicit timeouts, no retries, everything degrades to a logged warning, and `endpoint_for_type`
tolerates malformed packets.

---

## Spec-vs-Code Drift

| Claim | Source | Reality |
|---|---|---|
| "All receipts MUST validate against `docs/canonical/receipt.schema.v1.json`... before database insertion" | `docs/canonical/receipt.rules.md:236` | `validation.py:211` reads `spec/receipt.schema.v1.json`; no `spec/` dir; returns `[]` always (C2) |
| "`docs/canonical/receipt.schema.v1.json` is authoritative, and the examples under `examples/` are validated against it in CI" | `README.md:79-80` | Half true. `tools/validate_all_examples.py:24` globs `examples/receipts/*.json` only — the four negative fixtures in `examples/receipts/invalid/` are never run, so nothing asserts the schema *rejects* them |
| "Complete Pydantic models matching receipt.schema.v1.json" / "Schema Compliance ✅" | `CODE_REVIEW.md:104,22` | 11 demonstrated divergences (H4) |
| "JSON Schema validation ✅ PASS — Optional validation with graceful fallback" | `CODE_REVIEW.md:399` | The "graceful fallback" *is* the vulnerability; it fires 100% of the time |
| "Receipts are append-only" (Core Invariant 3) | `README.md:140` | No trigger, rule, REVOKE, or constraint in `schema/` or `docs/canonical/*.sql`. The only GRANTs are commented out (`schema/receipts.sql:151-153`) |
| "`phase` MUST be one of: accepted, complete, escalate" | `LegiVellum Integration Lock Spec v0.txt` §2.1; `receipt.schema.v1.json:118-122` | `docs/canonical/ReceiptGate/schema/001_receipts.sql:8` — `CHECK (phase IN ('accepted','complete','escalate','cancel'))` |
| `TERMINAL_RECEIPT_TYPES` must be an explicit set; terminator detection type-gated | `Gate v1 Exit Criteria Template.txt` §4 | Zero occurrences in `shared/`, `docs/canonical/`, `schema/` |
| `SYSTEM_PRINCIPAL_ID = "sys:legivellum"`, `SERVICE_PRINCIPAL_ID`, `owner_principal_id` ownership rules | `Gate v1 Exit Criteria Template.txt` §3 | Zero occurrences anywhere in the repo. Nine gates each told to invent them |
| "`shared/legivellum/` is mounted into the containers rather than vendored, so there is one copy of the bootstrap client instead of nine" | `README.md:131-133` | True for 4 of 8 demo services (`delegate`, `interrogate`, `asyncgate`, `cognigate`). `receiptgate`, `interview`, `depotgate`, `metagate` get no mount — their parent-walk loader finds nothing and silently skips bootstrap |
| Receipt IDs are client-generated ULIDs | `README.md:64`, `models.py:49-51` | Reference worker uses `receipt_id=str(uuid.uuid4())` (`examples/minimal_worker/minimal_worker.py:50`) |
| MetaGate/ReceiptGate/DepotGate at ports 8010/8090/8020 | `WORKER_QUICKSTART.md:22-28` | Demo stack publishes 8100/8300/8200 (`problemata_demo/docker-compose.yml`) |
| `CORS_ORIGINS=*` with "Set restrictive CORS_ORIGINS in production" | `.env.example:43,89` | No code in the repo reads `CORS_ORIGINS`; no `CORSMiddleware` anywhere in `shared/`, `tools/`, `problemata_demo/` |

### HIGH-9 — Three incompatible receipt storage models live in `docs/canonical/` + `schema/`

1. `docs/canonical/receipt.schema.v1.json` — 42 flat fields, `recipient_ai`, `from_principal`/`for_principal`, 3 phases.
2. `docs/canonical/ReceiptGate/schema/001_receipts.sql` — 13 columns, `obligation_id`, `recipient`, `created_by`, `body` JSONB, 4 phases (adds `cancel`).
3. `schema/receipts.sql` — 42 flat columns, a third variant, referenced only by `tests/conftest.py:79-83` (which also lists `schema/workers.sql`, a file that does not exist).

The live ledger uses none of these three exactly. `ReceiptGate/schema/005_receipts_v1.sql` defines
`receipts_v1` (10 columns + `payload` JSONB) — and `docs/canonical/ReceiptGate/schema/` contains only
001–004. **The canonical mirror of the ledger schema is missing the migration that implements the
canonical receipt.** A reader following `docs/canonical/` as the declared source of truth builds
against a table the ledger does not use.

`docs/canonical/receipt.schema.v1.json` and `ReceiptGate/schema/receipt.schema.v1.json` are byte-identical
(verified) — that one link holds.

### HIGH-11 — SQL CHECK constraints under-enforce `receipt.rules.md`, and immutability is enforced nowhere

`schema/receipts.sql:77-84`:

```sql
  CONSTRAINT phase_accepted_rules CHECK (
    phase != 'accepted' OR (
      status = 'NA' AND
      completed_at IS NULL AND
      task_summary != 'TBD' AND
      escalation_class = 'NA'
    )
  ),
```

`receipt.rules.md:27-35` requires eight more predicates for `accepted`: `outcome_kind = 'NA'`,
all three artifact fields `= 'NA'`, `escalation_to = 'NA'`, `retry_requested = false`.
`phase_escalate_rules` (line 95) omits `escalation_to != 'NA'` — only enforced when
`escalation_class = 'owner'` (line 110) — and omits the routing invariant `recipient_ai = escalation_to`,
which unlike JSON Schema *is* expressible as a SQL CHECK. `artifact_pointer_rules` (line 103) omits
`artifact_mime != 'NA'` that `receipt.rules.md:50` requires.

**Failure scenario:** `INSERT` a `phase='escalate'` receipt with `escalation_class='policy'`,
`escalation_to='NA'`, `recipient_ai='worker-7'`. All CHECKs pass. The receipt claims to transfer an
obligation to nobody while sitting in worker-7's inbox — `receipt.rules.md:58` says escalation ends the
issuer's obligation, so the obligation is now orphaned with no owner. Pydantic would have caught this
(`models.py:204-208`) but the DB is the layer that has to hold when a service bypasses the model, and C2
removed the schema layer entirely.

Immutability (Core Invariant 3): `grep -rn "BEFORE UPDATE|RULE|REVOKE"` across `schema/` and
`docs/canonical/**/*.sql` returns nothing. Any `UPDATE receipts SET outcome_text = ...` succeeds.

---

## `.standalone_code/` assessment

**Answer: a second source of truth that has diverged — committed, not gitignored, ~2 MB of stale
forked source from six sibling repos, last touched 2026-01-07 (seven months of drift).**

`.gitignore` does not mention it. It contains full source trees for AsyncGate, CogniGate, DepotGate,
MemoryGate, MetaGate, plus empty-ish DeleGate/InterView dirs — 100 of the repo's 161 Python files.

Measured divergence against the real repos at `/home/claude/lv/<Repo>/`:

| File | Vendored | Real | Delta |
|---|---|---|---|
| `MetaGate/src/metagate/auth/auth.py` | 157 | 206 | +49 |
| `MetaGate/src/metagate/config.py` | 47 | 131 | +84 |
| `MetaGate/src/metagate/services/bootstrap.py` | 288 | 341 | +53 |
| `AsyncGate/src/asyncgate/engine/core.py` | 993 | 1435 | +442 |
| `MemoryGate/server.py` | 1658 | 9 | upstream is now a shim |
| `DepotGate/src/depotgate/api/routes.py` | 403 | *file deleted upstream* | structure changed |

The MetaGate auth divergence is security-relevant. Vendored (`.standalone_code/MetaGate/src/metagate/auth/auth.py:39-41`):

```python
def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage/lookup."""
    return hashlib.sha256(api_key.encode()).hexdigest()
```

Real (`/home/claude/lv/MetaGate/src/metagate/auth/auth.py:51-58`):

```python
def hash_api_key(api_key: str) -> str:
    try:
        return bcrypt.hash(api_key)
    except Exception:
        if settings.debug:
            return hashlib.sha256(api_key.encode()).hexdigest()
        raise
```

The vendored copy is the pre-hardening version: unsalted single-round SHA-256 for credential storage,
and it also lacks `is_admin_principal()` (real file lines 42-48), the function that gates admin
endpoints. Anyone reading `.standalone_code/` to understand MetaGate's auth model learns a model
that was replaced because it was wrong.

Also committed under it: `.standalone_code/AsyncGate/.env.local` — an actual `.env.local`, not
`.env.example`, containing `ASYNCGATE_API_KEY=dev-test-key-not-for-production` and
`ASYNCGATE_ALLOW_INSECURE_DEV=true`. `.gitignore:6` claims `.env.*` is ignored; this file is in the
tree regardless, so the ignore rule is not doing what the operator thinks.

**Recommendation:** delete the directory. Nothing imports it (`grep` for imports crossing into
`.standalone_code` returns nothing outside itself), CI does not compile it (`compileall` and `ruff`
target `shared/legivellum` only), and the real repos are checked out beside this one by
`stack.yml`. If a frozen reference is genuinely wanted, pin git SHAs in a manifest instead of forking
100 files.

---

## Critical & High Findings

Summarised; detail above.

| ID | Sev | File:Line | Finding |
|---|---|---|---|
| C1 | CRITICAL | `shared/legivellum/auth.py:78` | `dev-key-*`/`test-key-*` wildcard authenticates as arbitrary tenant in all modes incl. strict |
| C2 | CRITICAL | `shared/legivellum/validation.py:211` | Schema path points at removed `spec/` dir; JSON Schema validation silently disabled system-wide |
| H1 | HIGH | `shared/legivellum/auth.py:156` | Attacker-controlled `Host` header proves "localhost"; AUTO is the default mode |
| H2 | HIGH | `shared/legivellum/auth.py:24` | Four hardcoded API keys in library source, honoured unconditionally |
| H3 | HIGH | `shared/legivellum/auth.py:51` | Unknown/typo'd auth mode falls back to the bypass mode; var absent from `DEPLOYMENT.md` |
| H4 | HIGH | `shared/legivellum/models.py:151` | Pydantic accepts 11 receipt shapes the canonical schema rejects (demonstrated) |
| H5 | HIGH | `shared/legivellum/problemata_control_ui.py:160` | Tenant authenticated then discarded; no scoping on list/get/upsert; cross-tenant topology overwrite |
| H6 | HIGH | `shared/legivellum/problemata_control.py:457`, `problemata_control_ui.py:47` | `parents[2]` + no package data ⇒ non-editable install cannot find migrations or UI assets |
| H7 | HIGH | `pyproject.toml:12` vs `shared/pyproject.toml:16` | Duplicate `legivellum` packages, different backends, `ulid-py` vs `python-ulid` — the latter breaks `ulid.new()` |
| H8 | HIGH | `.standalone_code/` | Committed 7-month-stale fork of 6 repos incl. pre-bcrypt MetaGate auth |
| H9 | HIGH | `docs/canonical/ReceiptGate/schema/001_receipts.sql:8`; missing `005_receipts_v1.sql` | Three incompatible receipt models in-repo; canonical mirror lacks the migration that implements v1; 4th phase `cancel` contradicts the Lock Spec |
| H10 | HIGH | `tests/test_asyncgate.py`, `test_delegate.py`, `test_memorygate.py` | 47 of 118 tests are `pass  # Placeholder` and report green |
| H11 | HIGH | `schema/receipts.sql:77` | CHECK constraints under-enforce `receipt.rules.md`; no immutability enforcement anywhere |
| H12 | HIGH | repo-wide | `SYSTEM_PRINCIPAL_ID`, `SERVICE_PRINCIPAL_ID`, `TERMINAL_RECEIPT_TYPES`, `owner_principal_id` defined nowhere in the substrate |

---

## Medium Findings

**M1 — `validate_receipt_create` disables schema validation explicitly.**
`shared/legivellum/validation.py:252` — `errors = validate_receipt(data, validate_schema=False)`.
Even after C2 is fixed, the one function that turns a `ReceiptCreate` into a `Receipt` skips the
canonical schema. Scenario: a gate uses `validate_receipt_create()` believing it is the full pipeline
(the name implies it), and gets only Pydantic + size checks.

**M2 — Negative examples are never exercised.**
`tools/validate_all_examples.py:24` — `receipt_files = sorted(examples_dir.glob("*.json"))`.
Non-recursive, so `examples/receipts/invalid/{artifact_pointer_na,complete_null_timestamp,missing_receipt_id,routing_invariant_violation}.json`
are skipped. Those four are the only conformance assertions the repo has that the schema *rejects*
anything, and CI runs none of them. A regression that loosens the schema passes CI green.
Line 40 also invokes `"python"` rather than `sys.executable`, and `Path("examples/receipts")` at line 17
is CWD-relative — the tool only works when run from repo root.

**M3 — Lazy repository startup race.** `problemata_control.py:338` (detail above).

**M4 — `close_database` leaves stale session factory.** `database.py:62` (detail above).

**M5 — `"pstryder"` as default tenant in three layers.** (detail above).

**M6 — Control UI entrypoint: `0.0.0.0` + `reload=True`, and builds the app twice.**
`tools/problemata_control_ui/server.py:3` does `from legivellum.problemata_control_ui import app`,
which triggers the PEP-562 `__getattr__` at `problemata_control_ui.py:197` and constructs a full
FastAPI app (mounting static files, constructing a Postgres repository) at import time — defeating the
laziness that module's docstring was written to provide. `tools/problemata_control_ui/__init__.py:3`
re-exports it, so merely importing the package builds an app. Then `uvicorn.run("...:app", reload=True)`
(line 8-13) re-imports the module in a worker and builds a second one. `host="0.0.0.0"` with
`reload=True` is a dev configuration in the shipped entrypoint; with the auth defaults in C1/H1 this is
an unauthenticated control plane on all interfaces.

**M7 — The mypy CI gate cannot fail.**
`.mypy-ci.ini` sets `follow_imports = skip` and
`disable_error_code = attr-defined,call-arg,arg-type,assignment,union-attr,no-any-return,valid-type,var-annotated,import-not-found,import-untyped,type-arg,no-untyped-call,untyped-decorator,misc,no-untyped-def`.
That is essentially every error class mypy emits. `.github/workflows/ci.yml:70` runs it and it will
always pass. Same shape for `ruff check --select E9,F63,F7,F82` (line 67) — syntax errors and undefined
names only. Neither would have caught anything in this review.

**M8 — Demo stack: 1 of 8 services has a healthcheck; three build no image.**
`problemata_demo/docker-compose.yml` — only `metagate` has a `healthcheck` among the eight services
(the four Postgres containers do). `depends_on: condition: service_started` therefore means "container
process spawned", not "ready". `receiptgate`, `interview`, `interrogate` run `image: python:3.11-slim`
with `command: pip install --no-cache-dir /app/<repo> && ...` — they never build the Dockerfile the
sibling repo ships, so the demo does not exercise the artifact that would be deployed, and every
`compose up` requires PyPI reachability. `metagate-seed` likewise `pip install`s asyncpg at runtime.
`wait_for_stack.py` compensates for the missing healthchecks and is well written, but it is a
workaround, and `stack.yml` is the only thing that runs it. `version: "3.9"` (line 1) is obsolete under
Compose v2. Every service pins `container_name`, so two stacks cannot coexist.

**M9 — `wait_for_stack` treats MCP tool errors as healthy.**
`problemata_demo/wait_for_stack.py:61` — `return "result" in body`. An MCP server answering
`{"result": {"isError": true, "content": [{"text": "database unreachable"}]}}` is JSON-RPC-successful
and satisfies this check. Scenario: ReceiptGate starts with an unmigrated DB, `receiptgate.health`
returns an error result, `wait_for_stack` prints "healthy", and `golden_path.py` fails a few seconds
later with a confusing downstream error instead of a clear readiness timeout.

**M10 — `conftest` schema bootstrap references a file that does not exist.**
`tests/conftest.py:79-83` lists `schema/workers.sql`; `ls schema/` shows `init.sql, migrations, plans.sql,
receipts.sql, tasks.sql`. Guarded by `os.path.exists` (line 87) so it silently skips, then line 105
drops the table it never created. Any test relying on a `workers` table would fail confusingly.

---

## Low / Nits

- **L1** `examples/minimal_worker/minimal_worker.py:50` — `receipt_id=str(uuid.uuid4())`. The reference
  implementation contradicts `README.md:64` and `models.py:49`, which specify ULID. Schema-legal
  (any non-empty string) but loses the lexicographic time-ordering ULIDs exist for.
- **L2** `examples/minimal_worker/minimal_worker.py:56` — worker sets `stored_at=_now()` client-side.
  `receipt.rules.md:146` makes `stored_at` the ledger clock and the source of truth for ordering; the
  reference worker teaches the wrong thing.
- **L3** `shared/legivellum/validation.py:17` — `print("Warning: jsonschema not installed...")` at import
  time; line 238 `print(f"Warning: JSON Schema validation error: {e}")` swallows every non-jsonschema
  exception. A library should log, not print, and should not silently swallow.
- **L4** `shared/legivellum/observability/__init__.py:12` — `ENABLED` is evaluated at import. A service that
  loads `.env` after importing the package gets metrics permanently off with no diagnostic.
- **L5** `shared/legivellum/observability/__init__.py:60-79` — docstring says metric names "will be prefixed
  with service name"; `prometheus.py:139` passes `name` through unprefixed. Also `METRICS_PORT`
  (`prometheus.py:19`) is read and only ever logged.
- **L6** `shared/legivellum/observability/prometheus.py:137-148` — `_counters`/`_histograms` are check-then-set
  globals with no lock, and the label key set is frozen by the first call. A second call with different
  label keys raises inside `labels(**label_values)`, is caught at line 152, and the observation is
  silently dropped.
- **L7** `shared/legivellum/problemata_control.py:427-448` — `list()` has no `LIMIT` and no pagination; the
  UI route at `problemata_control_ui.py:165` returns the whole registry.
- **L8** `shared/legivellum/validation.py:56` — `import json` inside `validate_field_sizes` when the module
  already imports it at line 6. Also `validate_field_sizes` skips list-valued fields entirely
  (`continue` at line 59), so `artifact_refs` is unbounded.
- **L9** `shared/legivellum/validation.py:23` — `field: str = None, constraint: str = None` typed as `str`
  but defaulted to `None`; should be `Optional[str]`. Invisible to CI because M7 disables `assignment`.
- **L10** `shared/legivellum/problemata_control.py:831-859` — hand-rolled SQL statement splitter. Handles
  single quotes and backslash escapes but not `$$`-quoted bodies, `E''` strings, or doubled `''`.
  Fine for the one migration present; a landmine for the first `CREATE FUNCTION`.
- **L11** `SPEC_COMPLIANCE_REPORT.md:26,61,102` — section headers still carry `F:\HexyLab\...` Windows paths
  and an "Appendix: components/" that describes a layout removed two refactors ago. Both legacy docs
  carry honest banners saying so, which is better than most, but they are still the first two documents
  a reviewer opens.
- **L12** `.env.example:21` — `LEGIVELLUM_API_KEY=dev-key-pstryder` and `:28` `LEGIVELLUM_AUTH_MODE=auto`.
  The example config ships the bypass mode and one of the hardcoded keys.
- **L13** `pytest.ini` sets no `--timeout` despite `pytest-timeout` being a declared dev dependency; CI
  relies on the 45-minute job timeout.

---

## Test Coverage Gaps

118 test functions across 12 files (the brief said 28 files; there are 12 plus `conftest.py`).

**What is covered well:** `test_metagate_bootstrap.py` (18 tests) is thorough — endpoint-type resolution,
explicit-config-wins, malformed packets, ack skipped on failure, timeouts. `test_problemata_control.py`
(12) and `test_problemata_publish.py` (7) cover the control plane's happy and refusal paths.
`test_models.py` (10) covers phase constraints and the routing invariant.

**Gaps, in order of what they let through:**

1. **Zero tests for `validate_json_schema`.** This is why C2 survived a rename that the repo itself
   documented. ReceiptGate wrote four tests for exactly this (`ReceiptGate/tests/test_validation.py`,
   `TestSchemaResolution`) including `test_missing_schema_raises_rather_than_passing_everything`. The
   shared library has none. Port those four tests.
2. **47 placeholder tests report green.** `test_asyncgate.py` 18/18, `test_delegate.py` 18/18,
   `test_memorygate.py` 11/11 are all `pass  # Placeholder`. Example (`test_asyncgate.py:44-49`):
   ```python
       async def test_create_task(self, sample_task):
           """POST /tasks creates task and returns task_id"""
           # POST to /tasks
           # Verify 201 response
           pass  # Placeholder
   ```
   `CODE_REVIEW.md:415-421` counts these as *"Test Coverage ✅ SUBSTANTIALLY IMPROVED... 1,200+ lines,
   structure production-ready"*. 40% of the suite asserts nothing while inflating the pass count. Delete
   them or mark `@pytest.mark.skip(reason=...)` so the count is honest.
3. **No conformance suite for the canonical schema.** `test_models.py:192` is a single positive case
   (`jsonschema.validate(receipt.model_dump(), schema)` on one hand-built `accepted` receipt). There is no
   parametrised sweep of the schema's `allOf` branches, and no test asserting the Pydantic model and the
   JSON Schema agree — the property whose violation is H4. Note it also uses `model_dump()` rather than
   `model_dump(mode="json")`; it passes only because every timestamp in that fixture is `None`.
4. **`examples/receipts/invalid/` is asserted nowhere.** Not in CI (M2), not in the test suite.
5. **No test that strict mode rejects an unregistered key.** `test_auth.py` has four tests; two of them
   assert the C1 bypass works. A `test_strict_mode_rejects_unregistered_dev_key` would have failed on day one.
6. **README invariants are not asserted anywhere.** Immutability (no test that UPDATE is refused),
   Authority (no test that a non-Principal/non-DeleGate cannot mint), Derived State (no test that inbox
   is query-derived). `problemata_demo/invariant_probe.py` is the only adversarial coverage in the repo
   and it runs only in the `stack.yml` workflow against live containers, not in unit CI.
7. **Nothing tests the file-path loading contract the nine gates actually use.** All nine load
   `metagate_bootstrap.py` via `importlib.util.spec_from_file_location` after a parent-directory walk.
   `test_metagate_bootstrap.py` imports it normally. A signature change would pass CI here and warn-and-degrade
   in nine repos.

---

## Cross-repo observations

- **The C2 fix exists and was not propagated.** `ReceiptGate/src/receiptgate/validation_v1.py:79-95`
  fixes the fail-open schema resolution and documents why, with a regression test. The shared library
  it was forked from is unchanged. This is the pattern the whole stack should worry about: fixes flow
  outward from the copies, never back to the source. Same shape as H6 (`parents[2]`), which
  `stack.yml:8-11` names as a bug already fixed in ReceiptGate but which is still live twice in
  `shared/legivellum/`.
- **`shared/` is consumed by exec-of-a-file-path, not by a dependency.** Nine repos do
  `importlib.util.spec_from_file_location(...)` on `LegiVellum/shared/legivellum/metagate_bootstrap.py`
  after walking parents, with `except Exception: return None`. There is no version, no pin, no contract
  test. Combined with the module's "bootstrap must never block startup" rule, a breaking change here
  produces nine `WARNING` lines and nine services running on unbootstrapped config — never a failure.
  This is the single highest-leverage structural risk in the stack and it is this repo's to fix
  (publish a versioned wheel; add a consumer contract test).
- **JWT audience verification is off in MetaGate**, in both the real repo and the vendored copy:
  `options={"verify_aud": False}` (`MetaGate/src/metagate/auth/auth.py:73` and
  `.standalone_code/MetaGate/src/metagate/auth/auth.py:51`). Flagging for the MetaGate reviewer; the
  vendored copy means the pattern gets read twice.
- **`ReceiptGate`'s `_BINDING_SPECS` is an empty tuple** (`ReceiptGate/src/receiptgate/metagate_client.py:31`),
  so ReceiptGate resolves nothing from MetaGate. Consistent with it being the ledger, but worth
  confirming with the ReceiptGate reviewer that bootstrap is intentionally a no-op there.
- **The demo stack does not run the shipped images for three services.** `receiptgate`, `interview`,
  `interrogate` are `pip install`ed into `python:3.11-slim` rather than built from their Dockerfiles, so
  `stack.yml` — the workflow written precisely to catch container bugs — does not test those three repos'
  containers.
- **The Exit Criteria template's principal/terminal-receipt vocabulary exists in no repo's shared code.**
  `owner_principal_id`, `obligation_id`, `TERMINAL_RECEIPT_TYPES`, `ack`/`progress`/`anomaly` are the
  template's model; `receipt.schema.v1.json` has `for_principal`/`recipient_ai` and three phases. Reviewers
  of the other nine repos should expect each to have invented its own reconciliation. `obligation_id`
  appears in four `docs/canonical/` files and in zero schema fields.

---

## What's solid

- `shared/legivellum/metagate_bootstrap.py` is the best file in the repo. Explicit timeout, no retry
  storm, never raises, degrades to data rather than control flow, tolerates malformed packets
  (`endpoint_for_type`, line 93), and `_same_endpoint` (line 74) exists because someone thought about
  operators ignoring noisy log lines. The module docstring explains *why* rather than *what*. 18 real
  tests behind it.
- `.github/workflows/stack.yml` is unusually good CI. It checks out nine sibling repos, builds and runs
  the assembled stack, runs six behavioural paths plus an adversarial invariant probe, masks seeded
  credentials with `::add-mask::`, dumps container logs on failure, and tears down with `-v`. The header
  comment names the three specific container bugs that motivated it. Most stacks this size have nothing
  like this.
- `problemata_demo/invariant_probe.py` (396 lines) is adversarial-by-construction: each probe sends
  something the canonical specs say MUST be refused and passes only on refusal. That is the right shape
  for testing a rules-based substrate.
- `problemata_demo/wait_for_stack.py` names exactly which service never came up, so CI failures are
  readable without digging through logs.
- Migration handling in `problemata_control.py:461-527` — SHA-256 checksums stored per
  `(component, version)` and a hard failure on mismatch, so an edited applied migration is caught rather
  than silently diverging.
- All SQL in `problemata_control.py` is properly parameterised; the only f-string interpolations
  (lines 476, 501, 522) are module constants. No injection found in `schema/` or `tools/` either.
- The legacy banners on `CODE_REVIEW.md` and `SPEC_COMPLIANCE_REPORT.md` correctly warn that their paths
  predate the `spec/` → `docs/canonical/` move. The docs were honest; the code was not updated to match.

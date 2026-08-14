# LEGIVELLUM_STORY.md

**Purpose:** A working “story + demo script” for LegiVellum. Treat this as a living sales/README companion: crisp narrative, repeatable demo, and the exact claims we’re proving.

> LegiVellum is **receipt-driven coordination infrastructure**: a substrate for building agentic pipelines where responsibility cannot move silently, time cannot trap cognition, and outcomes remain provable after restarts.

---

## 0) The one-liner (say this first)

LegiVellum is an auditable automation substrate for agent pipelines: it coordinates work using **immutable receipts** (accept/complete/escalate), so you can always answer **what happened, who owned it, what artifacts were produced, and what’s still owed**—even when workers die, processes restart, and execution goes async.

---

## 1) The problem (the enterprise backend-AI reality)

Modern orgs are increasingly using AI **only on the backend**:
- no direct chat interface
- constrained surfaces
- strict policies
- workflows that run as services/batch jobs

That’s the *safe* pattern. But it creates a new failure:

### The observability gap
After the AI workflow runs, teams can’t reliably answer:
- *What actually happened?*
- *Which component accepted responsibility for what?*
- *What was produced, and where is it?*
- *What failed, what retried, what escalated?*
- *What remains unresolved?*

Traditional logs don’t solve this:
- logs aren’t a protocol
- logs don’t encode custody/obligation transfer
- logs don’t form a causality chain
- logs don’t provide a durable, queryable “global narrative”

**LegiVellum’s claim:** receipts are the missing global narrative.

---

## 2) What LegiVellum is / is not

### It **is**
- **cognitive infrastructure** (not an agent framework)
- a set of **composable primitives** with explicit authority boundaries
- a **receipt protocol** that makes responsibility transfers provable
- an architecture that survives: worker death, restarts, topology changes

### It **is not**
- a central orchestrator
- a hidden master controller
- a records system / system-of-record replacement
- “AI magic” or a chat UX

**Core axiom:** *Receipts are the only global narrative. Everything else is local behavior.*

---

## 3) Product surfaces & personas (vision)

LegiVellum’s long-term product form is **one substrate** with **three human-facing surfaces** and **one agent-facing surface**.

### 3.1 Admin / Ops Dashboard (operators)
Purpose: keep the substrate governable and healthy.
- tenancy/projects
- principals/agent registry
- capability + budget/quota policy
- service health (AsyncGate queue depth, MemoryGate health, storage health)
- alerts + audit export

### 3.2 Receipt / Task Explorer (stakeholders, business owners)
Purpose: answer “what happened?” without reading logs or code.
- search by task/doc/customer/case
- timelines (accepted → complete/escalate chains)
- attached artifacts (pointers + hashes)
- open obligations (what’s still owed)
- **read-only** by default (InterView rules)

### 3.3 Problemata Builder/Manager (builders)
Purpose: create and manage **Problemata** (cognitive worker circuits) that the substrate can instantiate and execute.
- versioned Problemata definitions
- I/O schemas, invariants, required capabilities
- composition into stages (extract → classify → enrich → route)
- test harness + replay (“golden path”)
- publish/approve to a catalog

**Principle:** *spec-first*. The canonical artifact is a spec that is diffable, reviewable, and generatable by agents.

### 3.4 API (agents + systems)
Purpose: everything is automatable.
- create/update Problemata specs
- instantiate runs
- query receipts + derived state

**Important:** the UI wrapper is for humans exclusively; agents should operate on the spec/API.

---

## 4) The demo (flagship use case)

### Demo name
**Dark Data Curation Pipeline (with Receipts)**

### Demo goal
Show a repeatable, controlled, auditable agent pipeline that:
1) ingests unstructured files
2) interrogates them (extract, classify, enrich)
3) outputs structured metadata + signals + artifacts
4) persists outputs to a destination repository
5) produces receipts that explain the workflow and custody

This is a **data curation** system, not records policy enforcement.

### What this demo proves (explicit claims)
- **Nothing that matters happens silently** (receipt at obligation boundaries)
- **Authority is explicit** (only Principals/DeleGates mint obligations)
- **Time is neutral** (long work crosses Async boundary; no blocking)
- **Artifacts are governed** (pointers + hashes; durable outputs)
- **The system remains explainable after failure** (receipt chain + derived state)

---

## 4) Actors & primitives (demo topology)

### Minimal topology (golden path)
- **Principal:** `principal:file-curation` (or similar)
- **DeleGate:** generates a Plan (optional for v0 demo; recommended for v1)
- **AsyncGate:** parks and leases work
- **Worker/CogniGate-like executor:** performs extraction/classification/enrichment
- **MemoryGate:** stores receipts (append-only; derived state)
- **DepotGate (or stand-in):** stores artifacts (raw text, JSON outputs, bundles)
- **InterView/control plane:** read-only introspection UI over derived state

### Two compositions (same primitives, different wiring)

**A) Lights-Out Curation**
- auto-route on confidence >= threshold and sensitivity <= threshold

**B) Assisted Curation (HITL)**
- low confidence OR high sensitivity -> Review Queue
- human edits/approves -> continue pipeline
- human action becomes a receipted obligation boundary

---

## 5) Demo inputs and outputs

### Inputs (v0)
- A folder/bucket of mixed files (PDF/DOCX/TXT)
- include at least:
  - 1 clean text-heavy doc
  - 1 scanned/low-text PDF
  - 1 doc containing PII-ish patterns (for “sensitivity signal”)

### Outputs (curation payload)
For each document, produce (minimum viable):
- `fingerprint`: hash, size, mime, page count
- `extraction`: extracted text pointer + quality score
- `classification`: doc_type + confidence
- `entities`: org/person/date/amount (best-effort)
- `sensitivity_signals`: PII-ish flags + confidence
- `routing_hints`: recommended destination tags (non-authoritative)

### Artifact set (stored)
- `raw_text.txt` (or equivalent)
- `curation.json`
- optional: `preview.txt` / `thumbnail.png`
- optional: `audit_bundle.zip` (original + outputs + receipts)

---

## 6) Demo script (5–8 minutes)

### 6.1 Pre-demo setup (do this before the call)
- Start services (or mocked stand-ins): MemoryGate, AsyncGate, artifact store
- Ensure the control plane can show:
  - queue/run list
  - doc detail view
  - receipt timeline view
  - review queue (if HITL mode enabled)
- Put demo files into the intake source (or keep them ready to drop live)

### 6.2 Opening (30 seconds)
Say:
> “This is not an agent framework. It’s a substrate for building agent pipelines that can prove what happened. The core mechanism is receipts: accept / complete / escalate.”

### 6.3 Run the pipeline (2 minutes)
1) Drop 3–5 files into intake.
2) Show the system creating **accepted** receipts per document/task.
3) Show tasks crossing the async boundary (queued/leasing).

### 6.4 Show outcomes + artifacts (2 minutes)
For one “clean” doc:
- open doc detail
- show extracted text artifact pointer
- show `curation.json` (doc_type + confidence + entities)
- show **complete** receipt referencing artifacts

### 6.5 Show failure / escalation (1–2 minutes)
Pick a “hard” doc (scanned/garbled):
- show extraction quality low
- demonstrate policy: route to review OR escalate
- show **escalate** receipt with class `capability` or `policy` and a real reason
- show the continuation pattern: a new accepted task linked via parent/caused_by

### 6.6 Show HITL gate (optional but powerful) (1–2 minutes)
Switch to Assisted mode or show that it was already configured:
- doc enters Review Queue due to low confidence/high sensitivity
- human edits doc_type or confirms routing hint
- human “approve” action emits a receipt boundary (accepted -> complete)

### 6.7 Closing (30 seconds)
Say:
> “The value isn’t that the model guessed the doc type. The value is that this pipeline is repeatable, controlled, auditable, and explainable after failure. Receipts are the global narrative.”

---

## 7) The story to tell (verbatim-ish)

### 7.1 Context
“Enterprises are increasingly doing AI the safe way: backend-only workflows, no chat UI, constrained surfaces. The unintended consequence is an observability gap—after the system runs, nobody can confidently answer what happened.”

### 7.2 The wedge
“LegiVellum solves that gap structurally. It forces responsibility to be explicit and durable through receipts. Receipts aren’t logs—they’re proof of custody: accepted, complete, or escalate.”

### 7.3 Why it matters
“When something fails—compliance review, incident response, cost blowup, bad output—you don’t want folklore and log archaeology. You want a queryable narrative that tells you which component owned what, what artifacts were produced, and where the chain broke.”

### 7.4 What we’re not doing
“We are not replacing your records system, DMS, or ECM. We enrich unstructured content and emit structured outputs + provenance so downstream systems can manage it intelligently.”

---

## 8) Key objections and tight answers

### “Isn’t this just workflow orchestration?”
No. Orchestration assumes a central coordinator. LegiVellum’s coordination is protocol-first: receipts + explicit authority boundaries. No hidden master.

### “Isn’t this just logging?”
No. Logging is incidental, inconsistent, and non-normative. Receipts are a contract: the only global narrative used for coordination, recovery, and explanation.

### “Why not just use X (Temporal/Airflow/etc.)?”
Those are great at scheduling and workflows. LegiVellum is about **responsibility custody** and **auditability** across agentic delegation, tool use, and async execution—especially where cognition and authority must be separated.

### “Where does the money come from?”
Open source framework + paid control plane: dashboards, policy gates, review queues, audit export, tenancy/RBAC/SSO, alerts, managed hosting/support.

---

## 9) MVP checklist (for the demo to be credible)

### MUST
- Receipt schema and rules enforced (accepted/complete/escalate semantics)
- Derived state queries (inbox/timeline/chain)
- Artifact pointers/hashes stored and viewable
- At least one escalation path demonstrated
- Control plane shows receipt timeline per doc/task

### SHOULD
- HITL review queue with a simple threshold policy
- “Audit bundle” export (zip) for a single doc
- Clear cost/time counters per run

---

## 10) Notes / placeholders
- Decide whether the demo is “Plan-driven” (DeleGate produces a Plan) or “Principal-driven” (Principal mints tasks directly). For v1 credibility, Plan-driven is better.
- Keep “receipts” as the internal name; label the UI section **Audit Trail / Chain of Custody** if needed.

---

**Last updated:** 2026-02-07

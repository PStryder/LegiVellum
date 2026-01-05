# LegiVellum: The Permanent Record of Recursive Cognition

**A System Architecture for AI Agents That Remember, Scale, and Prove Their Work**

---

**Version:** 1.0  
**Date:** 2026-01-04  
**Status:** Complete Architecture Specification  
**Authors:** PStryder (Technomancy Laboratories), with Kee (Claude) and Hexy (ChatGPT)

---

## Executive Summary

LegiVellum is a system architecture that enables **recursive cognition across AI agents, systems, and time**. It solves the three fundamental problems that plague AI agent systems: **amnesia** (sessions don't build on each other), **blocking** (long tasks stop thinking), and **chaos** (delegation becomes guesswork).

The architecture consists of **three core primitives** that separate concerns usually tangled together:

1. **MemoryGate** — Durable semantic memory (what you know)
2. **AsyncGate** — Execution coordination (what you're working on)
3. **DeleGate** — Pure planning (what you decide to do next)

These three primitives are connected by a **coordination protocol** called **Receipts** — universal proof-of-action that turns time from an enemy into a neutral factor.

**Critical architectural principle:** LegiVellum does not replay receipts to reconstruct state; it uses receipts to prove that state transitions already occurred elsewhere. Receipts are proof, not process.

Together, these components create a system where:
- Sessions build on prior sessions instead of resetting
- Long-running work doesn't block cognitive cycles
- Delegation scales across tiers without chaos
- Every outcome traces back to origin through explicit chains

This is not another "smart agent framework." This is systems thinking applied to cognition — treating memory, execution, and planning as separable concerns that can evolve independently.

**The result:** Recursion stops being a parlor trick and becomes architecture.

---

## Table of Contents

1. [The Problem: Three Fundamental Flaws](#the-problem)
2. [The Solution: Three Primitives + Coordination](#the-solution)
3. [MemoryGate: The Permanent Record](#memorygate)
4. [AsyncGate: The Execution Coordinator](#asyncgate)
5. [DeleGate: The Pure Planner](#delegate)
6. [Receipt Protocol: Universal Accountability](#receipts)
7. [Integration Patterns](#integration)
8. [Complete Flows](#flows)
9. [Use Cases](#use-cases)
10. [Implementation Path](#implementation)
11. [Design Principles](#principles)
12. [Conclusion](#conclusion)

---

<a name="the-problem"></a>
## 1. The Problem: Three Fundamental Flaws

If you've built or used AI agents for anything serious, you've encountered these limitations:

### Amnesia

Sessions don't build on each other. You can have a breakthrough, end the session, and come back tomorrow only to start from scratch. Any sense of continuity is fragile, manual, or imaginary.

The agent doesn't remember what it learned. It can't build on prior work. Every session is Day One.

### Blocking

Agents are terrible at waiting.

If a task takes minutes or hours, the agent either blocks the entire session (wasting cognitive cycles) or loses track of the work altogether (breaking continuity). Long-running tasks and real thinking don't coexist cleanly.

The agent can't delegate work and move on. It's trapped waiting for results.

### Chaos

Delegation looks promising—until you try it.

One agent calls another, which calls another, which half-remembers something, which sends a message somewhere, and suddenly no one knows:

* who owns the task
* where the result went  
* or whether it already finished

We keep trying to build a single, smarter omni-agent.

What we actually need are **three focused supporting systems for cognition.**

---

<a name="the-solution"></a>
## 2. The Solution: Three Primitives + Coordination

The breakthrough wasn't adding intelligence. It was **drawing hard boundaries**.

Remembering, working, and deciding are different jobs — and most agent systems fail because they force one component to do all three at once.

When memory is treated like execution, agents cling to context they shouldn't, dragging stale assumptions forward. When execution is treated like cognition, long tasks block thought and erase momentum. When decision-making is mixed with either, delegation collapses into guesswork and hope.

**Separating these jobs wasn't an optimization. It was a correction.**

Once remembering was allowed to be durable but passive, working was allowed to be slow but reliable, and deciding was allowed to be lightweight but authoritative, each component became simpler. More importantly, their **failures stopped compounding**.

The system didn't become smarter. It became **stable**.

And once stability exists, intelligence can finally accumulate instead of resetting or unraveling.

### The Three Core Primitives

**MemoryGate** — What you know  
**AsyncGate** — What you're working on  
**DeleGate** — What you decide to do next

### The Coordination Protocol

**Receipts** — Universal proof-of-action

Receipts are not a fourth primitive. They are the **protocol** that connects the three primitives without chaos:
- When DeleGate creates a plan → receipt to MemoryGate
- When AsyncGate queues work → receipt to MemoryGate
- When work completes → receipt (with pointer) to MemoryGate
- Agents discover work, results, and state by querying MemoryGate's receipts

**One source of truth:** MemoryGate stores all receipts. The other components emit them.

> Separate remembering, working, and deciding — and each can scale without breaking the others.

---

<a name="memorygate"></a>
## 3. MemoryGate: The Permanent Record

**MemoryGate is durable semantic memory across sessions — and it is the source of truth for the entire system.**

Not chat logs. Not transcripts. Not token buffers.

**Meaning.**

MemoryGate holds the authoritative record of what is known, what has happened, and what currently requires attention for *every* agent it services. It provides a **universal bootstrap**: whenever any agent starts, restarts, or resumes work, MemoryGate is where it goes to reconstruct reality.

This makes MemoryGate the shared world-model for a cluster of agents and devices. It manages access to accumulated knowledge about the environment they operate in — prior discoveries, named concepts, learned patterns, referenced documents, and outstanding signals — without embedding itself in execution or decision-making.

### What MemoryGate Stores

MemoryGate stores *what mattered*, not *everything that happened*:

**1. Observations** — things learned or discovered
- Statements of fact derived from experience
- Evidence-backed insights
- Confidence levels (0.0-1.0)
- Domain categorization

**2. Patterns** — recurring structures that proved useful
- Synthesized understanding across observations
- "When X happens, Y tends to follow"
- Confidence and supporting evidence

**3. Concepts** — stable ideas worth naming and reusing
- Named entities with descriptions
- Relationships between concepts (enables/part_of/implements)
- Concept graphs for traversal

**4. Documents & References** — pointers to artifacts, not the artifacts themselves
- Summaries and key concepts
- Canonical storage locations (Google Drive, S3, etc.)
- Metadata for retrieval

**5. Receipts (The Permanent Ledger)** — proof of every meaningful action
- What happened (event_type, summary)
- Who owns it (recipient_ai)
- Where artifacts are (artifact_pointer, artifact_location)
- What's next (requires_action, suggested_next_step)
- Complete chains (caused_by_receipt_id for provenance)

**6. A Unified Inbox** — signals that require attention, not telemetry spam
- Unpaired receipts (open obligations)
- Returned via bootstrap
- Explicit ownership (one recipient_ai per receipt)

### What MemoryGate Does NOT Do

Just as importantly, MemoryGate is explicit about what it **does not** do.

MemoryGate does **not**:
- Execute tasks
- Track work-in-flight (AsyncGate's job)
- Manage retries or progress
- Decide what should happen next (DeleGate's job)
- Store raw outputs by default

It never blocks. It never schedules. It never reasons about plans.

### Passivity is the Point

Crucially, MemoryGate is **passive**.

When external systems post receipts, MemoryGate does not reply with progress updates, follow-ups, or derived state. It acknowledges only one thing: that the receipt was **received and stored**. That acknowledgment is final. There is no conversational back-and-forth, no hidden workflow, no implicit status machine.

The only time MemoryGate speaks is on **bootstrap** and **explicit query**. On bootstrap, it reports what is known and what is waiting. On query, it returns exactly what was asked for — no more, no less.

This restraint is what allows MemoryGate to remain trustworthy. It never speculates. It never interpolates. It never advances state on its own.

**MemoryGate remembers so agents can act — not the other way around.**

### The Bootstrap Contract

When a session starts, the agent does not reconstruct context by reenacting the past. Instead, it **bootstraps its state directly from MemoryGate**.

Bootstrap returns:
- Observations and patterns (prior insights)
- Concepts and documents (named knowledge)
- Receipt configuration (how to emit receipts)
- Cluster topology (connected services)
- **Active inbox** (unpaired receipts requiring attention)
- Unpaired count (open obligations)

Prior insights are recalled as durable knowledge rather than fragile conversation. Active signals surface in the inbox as explicit items requiring attention. Continuity resumes immediately, without ritual, guesswork, or repetition.

This is the difference between **continuity and nostalgia**. The agent does not relive yesterday's conversation or drag forward stale context wholesale. It resumes from what mattered, carrying forward meaning without inheriting momentum-killing baggage.

**No amnesia. No pretending. Real continuity — without dragging yesterday's context into today's decisions.**

### Core Tools

```python
# Session start - get current state
bootstrap = memory_bootstrap("AgentName", "Claude")
# Returns: observations, patterns, concepts, receipts, inbox, config

# Store insights
memory_store(
    observation="Discovery about X",
    domain="research",
    confidence=0.9,
    evidence=["source1", "source2"]
)

# Recall relevant knowledge
memory_recall(
    domain="research",
    min_confidence=0.7,
    limit=10
)

# Search across all types
memory_search(
    query="compression theory",
    limit=5
)

# Read inbox receipt
receipt = read_inbox_receipt(receipt_id)

# Archive processed receipt
archive_inbox_receipt(receipt_id)
```

### MemoryGate's Role in Receipt Protocol

MemoryGate is the **single-writer receipt store**:
- All components POST receipts to MemoryGate (via internal API)
- MemoryGate validates schema on receipt
- MemoryGate auto-pairs completion receipts with roots
- MemoryGate returns receipts in bootstrap and query
- **MemoryGate never volunteers state updates**

This makes MemoryGate the authoritative ledger for what happened, who owns what, and where things are.

---

<a name="asyncgate"></a>
## 4. AsyncGate: The Execution Coordinator

**AsyncGate exists to do one thing well: hold work while time passes.**

It does not execute that work itself. It does not think, decide, or reason about outcomes. AsyncGate is passive by design.

It maintains a durable queue of work, hands tasks out when asked, and **emits receipts (with pointers) when work completes**. Not guesses. Not inbox clutter. Actual, inspectable pointers embedded in receipts stored in MemoryGate.

AsyncGate handles the part most agents — and most humans — are terrible at: **waiting without forgetting**.

### What AsyncGate Does

**1. Task Queue Management**
- Accept tasks from Principals and DeleGates
- Assign tasks to workers via lease protocol
- Track active work (what's currently executing)

**2. Worker Coordination**
- Lease protocol (workers claim tasks)
- Heartbeat protocol (workers prove liveness)
- Completion protocol (workers return result pointers)
- Retry logic (task fails, release back to queue)

**3. Receipt Emission**
- When task queued → emit receipt (task_queued) to MemoryGate
- When task completes → emit receipt (task_complete, includes pointer) to MemoryGate
- When task fails → emit receipt (task_failed) to MemoryGate

**4. ResultChannel Abstraction**
- Workers store results in channels (email, S3, blob, file)
- Workers return pointer to AsyncGate
- AsyncGate passes pointer through in receipt
- Agents fetch results directly using pointer (not through AsyncGate)

### What AsyncGate Does NOT Do

AsyncGate does **not**:
- Decide *what* work should be done (DeleGate's job)
- Decompose tasks into subtasks (DeleGate's job)
- Reason about priorities or intent (DeleGate's job)
- Synthesize results (Agent's job)
- Store long-term knowledge (MemoryGate's job)
- **Maintain a queryable registry of pointers** (MemoryGate's job)

It doesn't plan. It doesn't remember meaning. It doesn't pretend to be intelligent.

### Critical Boundary: Workers Execute, They Don't Delegate

**The Discriminator:** If a component can create new tasks for other components, it's a DeleGate. If it can only execute what it's given, it's a Worker.

Workers execute under AsyncGate's lifecycle management:
1. Lease tasks from AsyncGate
2. Execute internally (no sub-delegation)
3. Return result pointer to AsyncGate
4. AsyncGate emits receipt to MemoryGate

Workers **cannot**:
- Call `queue_task()` to create tasks for other workers
- Decompose their assigned task into subtasks
- Route work to other workers

**AsyncGate is the execution coordinator, not a delegation layer.**

### The Agent Workflow

```
1. Agent: queue_task() → AsyncGate
2. AsyncGate: emit receipt (task_queued) → MemoryGate
3. Worker: lease → execute → complete with pointer → AsyncGate
4. AsyncGate: emit receipt (task_complete, includes pointer) → MemoryGate
5. Agent: bootstrap → read receipt from MemoryGate
6. Agent: extract pointer from receipt → fetch result directly
```

**Agents never query AsyncGate for pointers. Pointers live in receipts, receipts live in MemoryGate.**

### With AsyncGate in Place

- Long tasks don't block thinking — the agent can move on immediately
- Results don't disappear when sessions end or reset
- "Where's that thing I asked for three days ago?" has a concrete, inspectable answer
- Work survives session resets because receipts persist

AsyncGate doesn't answer *what should happen next*.

It guarantees that whatever *did* happen can be found again — even if hours pass, sessions reset, or the agent goes elsewhere in the meantime.

### Core Tools (MCP Interface for Agents)

```python
# Queue async work
result = queue_task(
    task_type="model_consultation",
    params={"prompt": "...", "models": ["gpt-4", "claude"]},
    recipient_ai="AgentName",
    caused_by_receipt_id="R.20260104_100000.kee.task_1"  # Chain from origin
)
# Returns: task_id, estimated_runtime_seconds, receipt_id

# Workers fetch results directly using pointer from receipt
# (not through AsyncGate)
receipt = memorygate.read_inbox_receipt(receipt_id)
pointer = receipt.artifact_pointer  # e.g., "s3://bucket/result.json"
channel = receipt.artifact_location  # e.g., "s3"
result = channel_client.fetch(channel, pointer)
```

### Worker Interface (FastAPI for Systems)

```python
# Worker leases task
POST /workers/lease_task
Body: {"worker_id": "worker-001", "task_types": ["code_analysis"]}
Returns: {task_id, task_type, params, run_id, lease_expires_at}

# Worker reports progress
POST /workers/heartbeat
Body: {"task_id": "...", "run_id": "..."}

# Worker completes with pointer
POST /workers/complete
Body: {
    "task_id": "...",
    "run_id": "...",
    "result_pointer": "s3://bucket/result.json",
    "result_channel": "s3",
    "summary": "Analysis complete, found 3 issues"
}
# AsyncGate emits receipt to MemoryGate with pointer embedded

# Worker reports failure
POST /workers/fail
Body: {
    "task_id": "...",
    "run_id": "...",
    "error_message": "...",
    "retryable": true
}
# AsyncGate emits receipt to MemoryGate
```

---

<a name="delegate"></a>
## 5. DeleGate: The Pure Planner

**DeleGate is where intelligence is intentionally allowed back into the system.**

It is the **pure planner** — the only component that reasons about intent, tradeoffs, and next actions.

**Intent in. Plan out.**

DeleGate exists to answer one question, and only one:

> *Given what we want to achieve, what should happen next?*

Crucially, DeleGate is designed so that nothing else can block it.

MemoryGate does not interrupt it with progress chatter. AsyncGate does not force it to wait on execution. Supporting components are deliberately passive so that DeleGate can form a plan, issue instructions, and then **move on** — either by ending its process entirely or by continuing with other cognitive work.

### What DeleGate Does

DeleGate takes intent — vague, high-level, or underspecified — and deterministically decomposes it into a structured plan:

**The Plan includes:**
- What can run immediately (direct worker calls)
- What must run asynchronously (queue via AsyncGate)
- What depends on what (execution order)
- What can be parallelized (independent steps)
- What needs escalation when done (reporting upward)

**The output of DeleGate is not conversation. It is not narration. It is a Plan that can be executed by agents, workers, or traditional systems without ambiguity.**

### What DeleGate Does NOT Do

Just as important as what DeleGate does is what it **refuses** to do.

DeleGate does **not**:
- Perform execution
- Wait on long-running tasks
- Track progress or retries
- Aggregate results
- Promote knowledge to memory

It never blocks. It never fetches artifacts. It never holds open state waiting for the world to respond.

This makes DeleGate compatible with a fully deterministic implementation. Given the same intent and the same world state (as exposed via MemoryGate), it can produce the same plan every time. Intelligence lives in planning, not in hidden side effects.

### Plan Structure

```json
{
    "plan_id": "plan-550e8400",
    "principal_ai": "AgentName",
    "intent": "Analyze the Python codebase and suggest optimizations",
    "created_at": "2026-01-04T10:00:00Z",
    "confidence": 0.9,
    
    "steps": [
        {
            "step_id": "step-1",
            "step_type": "queue_execution",  // Async via AsyncGate
            "worker_id": "code-analyzer-001",
            "tool_name": "analyze_repository",
            "params": {"repo_path": "/path/to/repo"},
            "depends_on": [],
            "estimated_runtime_seconds": 300
        },
        {
            "step_id": "step-2",
            "step_type": "wait_for",  // Wait for async completion
            "wait_for_step_ids": ["step-1"]
        },
        {
            "step_id": "step-3",
            "step_type": "call_worker",  // Direct execution
            "worker_id": "optimization-suggester-002",
            "tool_name": "suggest_optimizations",
            "params": {"analysis_pointer": "{{step-1.result_pointer}}"},
            "depends_on": ["step-2"]
        },
        {
            "step_id": "step-4",
            "step_type": "aggregate",  // Synthesis instruction
            "aggregate_step_ids": ["step-1", "step-3"],
            "synthesis_instructions": "Combine analysis with suggestions",
            "executor": "principal"  // Principal performs synthesis
        },
        {
            "step_id": "step-5",
            "step_type": "escalate",  // Final report
            "report_summary": "Code analysis complete",
            "recommendation": "Review suggestions and implement"
        }
    ],
    
    "estimated_total_runtime_seconds": 420
}
```

### Fractal Delegation

DeleGate can delegate to workers — or to **other DeleGates** — using the same contract at every level. That makes delegation **fractal**: departments can plan for sub-departments, which can plan for specialists, without special cases or hard-coded roles.

```
Principal AI → General Manager DeleGate
  ↓
General Manager DeleGate → Research Dept DeleGate
  ↓
Research Dept DeleGate → Worker Pool
```

Each tier uses the same contract. No special-casing. Arbitrary nesting.

### Core Tools

```python
# Create plan
plan = create_delegation_plan(
    intent="Analyze codebase and suggest optimizations",
    principal_ai="AgentName",
    caused_by_receipt_id="R.20260104_100000.kee.task_1"
)
# Returns: plan (structured), receipt_id
# Receipt emitted to MemoryGate

# Principal executes plan (not DeleGate)
for step in plan.steps:
    if step.step_type == "queue_execution":
        asyncgate.queue_task(...)  # Receipt emitted
    elif step.step_type == "call_worker":
        worker.call_tool(...)
    elif step.step_type == "wait_for":
        # Check MemoryGate inbox for receipts
        ...
    elif step.step_type == "aggregate":
        # Perform synthesis
        ...
```

DeleGate doesn't make the system smarter.

It makes intent **legible** — and legibility is what allows intelligence to scale without collapse.

---

<a name="receipts"></a>
## 6. Receipt Protocol: Universal Accountability

At the center of the system is a simple rule: **nothing that matters is allowed to happen silently**.

Every obligation lifecycle event produces a receipt. Not just completion. Not just failure. *Everything that changes accountability.*

Accepting work produces a receipt. Completing work produces a receipt. Escalating across boundaries produces a receipt.

A receipt is not the work itself. It is **proof of obligation**, who owns the outcome, and whether responsibility has been transferred.

### The Three Phases

Each receipt lifecycle has exactly three possible phases:

1. **accepted** — Creates an obligation for the issuer
2. **complete** — Resolves the obligation (success/failure/canceled)
3. **escalate** — Transfers responsibility across a boundary (ends issuer obligation)

**That's it.** No intermediate states. No progress updates. No "processing" phase.

State is **derived** from receipt history, not stored in receipts themselves:
- Task is **open** = `accepted` receipt exists, no `complete` receipt
- Task is **resolved** = `complete` receipt exists
- Task is **escalated** = `escalate` receipt exists

### Escalation: LegiVellum's Only Soft Push

Escalation is the **only mechanism** for cross-boundary coordination.

When a component cannot complete work (wrong capabilities, trust boundary, policy limit), it emits an `escalate` receipt routed to `recipient_ai = escalation_to`.

**Critical semantics:**
- Escalation **ends the issuer's obligation** for that task instance
- Escalation does NOT require its own completion receipt
- The new owner continues work by issuing NEW `accepted` tasks linked via `parent_task_id` and `caused_by_receipt_id`

This is **not delegation** (normal workflow breakdown). Escalation signals exceptional conditions: capability gaps, trust boundaries, policy violations.

Because receipts persist, time stops being an enemy. Hours can pass. Sessions can reset. Systems can go idle.

**Nothing important is lost, because nothing important happens without leaving a receipt behind.**

### Receipt Schema (Current)

**Example: Accepted Receipt**
```json
{
  "schema_version": "1.0",
  "tenant_id": "pstryder",
  "receipt_id": "01HTZQ8S3C8Y8Y1QJQ5Y8Z9F6G",
  "task_id": "T-123",
  "parent_task_id": "NA",
  "caused_by_receipt_id": "NA",
  
  "from_principal": "user.pstryder",
  "for_principal": "agent.kee",
  "source_system": "asyncgate",
  "recipient_ai": "kee",
  
  "phase": "accepted",
  "status": "NA",
  
  "task_type": "code.generate",
  "task_summary": "Generate React component",
  "task_body": "Create a login form component with validation",
  
  "expected_outcome_kind": "artifact_pointer",
  "expected_artifact_mime": "application/javascript",
  
  // Accepted receipts have no outcome yet
  "outcome_kind": "NA",
  "outcome_text": "NA",
  "artifact_pointer": "NA",
  "artifact_location": "NA",
  "artifact_mime": "NA",
  
  // Escalation fields NA for accepted
  "escalation_class": "NA",
  "escalation_to": "NA",
  
  "created_at": "2026-01-04T17:30:00Z",
  "stored_at": "2026-01-04T17:30:01Z",
  "started_at": null,
  "completed_at": null,
  
  "metadata": {}
}
```

**Example: Complete Receipt**
```json
{
  "schema_version": "1.0",
  "tenant_id": "pstryder",
  "receipt_id": "01HTZQ9A7J6Z3F7C5N8V1K2M3P",
  "task_id": "T-123",  // Same task_id as accepted
  
  "phase": "complete",
  "status": "success",  // Or "failure", "canceled"
  
  "outcome_kind": "artifact_pointer",
  "outcome_text": "Component generated successfully",
  "artifact_pointer": "s3://bucket/components/LoginForm.jsx",
  "artifact_location": "s3",
  "artifact_mime": "application/javascript",
  
  "completed_at": "2026-01-04T17:35:22Z",
  
  // ... other required fields
}
```

**Example: Escalate Receipt**
```json
{
  "schema_version": "1.0",
  "receipt_id": "01HTZQA2X9K4P8R7V3M2W5N6Q1",
  "task_id": "T-456",
  
  "phase": "escalate",
  "status": "NA",
  
  "escalation_class": "capability",
  "escalation_reason": "Requires database access (not available)",
  "escalation_to": "delegate",
  "recipient_ai": "delegate",  // Must match escalation_to
  
  // Escalation ends issuer obligation - no completion required
  "completed_at": null,
  
  // ... other required fields
}
```

**Key Schema Features:**
- Timestamps use `null` for "not applicable" (not "NA" strings)
- `tenant_id` is server-assigned from auth (prevents cross-tenant access)
- `receipt_id` uses ULID format (sortable, globally unique)
- Validation enforces phase-specific invariants
- See `/spec/receipt.schema.v1.json` for complete spec

### Provenance Chains

Every receipt (except root tasks from external input) can reference what caused it:

```
User input (task_id: T-root)
  → accepted by AsyncGate (caused_by_receipt_id: "NA")
  
DeleGate decomposes into subtasks
  → accepted (task_id: T-001, parent_task_id: T-root)
  → accepted (task_id: T-002, parent_task_id: T-root)
  
Worker completes T-001
  → complete (task_id: T-001)
  
Worker escalates T-002 (capability gap)
  → escalate (task_id: T-002, escalation_to: "delegate")
  
DeleGate accepts escalated work
  → accepted (task_id: T-003, caused_by_receipt_id: "escalate-receipt-id")
```

**Provenance Fields:**
- `parent_task_id` — Links delegated/spawned subtasks to parent
- `caused_by_receipt_id` — Links receipts in escalation chains

This creates a complete audit trail. Trace any result back through every decision and handoff that led to it.

### Derived State (No Explicit Pairing)

LegiVellum does NOT use "pairing fields" or mutable status flags.

Task status is **derived** from receipt queries:
- **Open** = `SELECT * FROM receipts WHERE tenant_id=? AND task_id=? AND phase='accepted' AND NOT EXISTS (SELECT 1 FROM receipts WHERE task_id=? AND phase='complete')`
- **Resolved** = `SELECT * FROM receipts WHERE tenant_id=? AND task_id=? AND phase='complete'`
- **Escalated** = `SELECT * FROM receipts WHERE tenant_id=? AND task_id=? AND phase='escalate'`

Components reconstruct state on demand. MemoryGate does not maintain "task status" or "pairs" as stored fields.

### Inbox Ownership: One Receipt, One Owner

**The Critical Invariant:** One receipt. One `recipient_ai`.

When a receipt is stored, exactly one agent owns it (`recipient_ai` field). That agent is *unambiguously responsible* for deciding what happens next.

**For accepted receipts:** The agent must eventually:
- Complete the task (`phase: complete`), OR
- Escalate to another agent (`phase: escalate`)

**For escalated receipts:** The receiving agent (`recipient_ai == escalation_to`) must:
- Issue new `accepted` tasks to continue the work
- Link them via `parent_task_id` or `caused_by_receipt_id`

This single rule eliminates failure modes:
- No shared inboxes where multiple agents race
- No "did you handle that?" uncertainty  
- No invisible handoffs where work dies
- No accidental duplication

**Receipts form a chain of custody.** At any moment, you can answer:
- *Who owns this?* → `recipient_ai`
- *Is it open?* → Query for `accepted` without `complete`
- *What decision is pending?* → Read the task from inbox

### Component Responsibilities

**AsyncGate emits:**
- `accepted` — When worker accepts a task from lease
- `complete` — When worker finishes (success/failure/canceled)
- `escalate` — When task timeout/retry limit exceeded (→ DeleGate)

**DeleGate emits:**
- `accepted` — When accepting escalated tasks
- `accepted` — For each subtask in decomposition (`parent_task_id` set)
- `escalate` — When decomposition exceeds scope (→ Principal)

**Principal emits:**
- `accepted` — When accepting user input
- `complete` — When finishing user-facing tasks
- `escalate` — When user decision required (if multi-tier)

**MemoryGate:**
- Receives all receipts (single-writer, validates, stores)
- Provides inbox queries (active `accepted` receipts)
- Provides bootstrap (config + inbox on session start)
- **Does NOT** interpret receipts or coordinate work

---

<a name="integration"></a>
## 7. Integration Patterns

### Session Initialization

Every session starts the same way:

```python
# 1. Bootstrap from MemoryGate
bootstrap = memory_bootstrap("AgentName", "Claude")

# Returns:
# - observations_count, patterns_count, concepts_count
# - receipt_config (format rules, event types)
# - connected_services (asyncgate_url, delegate_endpoints)
# - inbox_receipts (unpaired receipts requiring action)
# - unpaired_count (open obligations)

# 2. Check inbox for work-in-progress
if bootstrap['unpaired_count'] > 0:
    for receipt in bootstrap['inbox_receipts']:
        if receipt['event_type'] == 'task_complete':
            # Fetch result and process
            pointer = receipt['artifact_pointer']
            result = fetch_using_pointer(pointer)
            process_result(result)
            archive_inbox_receipt(receipt['receipt_id'])

# 3. Continue with new work or resume interrupted work
```

### Simple Direct Execution

For fast tasks (<5 seconds), call workers directly:

```python
# 1. Call worker (no AsyncGate)
result = worker.analyze_sentiment(text="...")

# 2. Process result immediately
# (No receipt needed for internal fast calls)
```

### Async Execution via AsyncGate

For long tasks (minutes/hours), use AsyncGate:

```python
# 1. Queue work
response = asyncgate.queue_task(
    task_type="model_consultation",
    params={"prompt": "...", "models": [10_models]},
    recipient_ai="AgentName",
    caused_by_receipt_id=current_receipt_id
)
# Returns: task_id, receipt_id
# Receipt emitted: task_queued

# 2. Continue other work (don't block)
think_about_other_problems()

# 3. Session ends (work continues in background)
# --- time passes ---

# 4. Next session: bootstrap shows completion
bootstrap = memory_bootstrap("AgentName", "Claude")
# inbox_receipts includes: task_complete receipt

# 5. Fetch result using pointer from receipt
receipt = bootstrap['inbox_receipts'][0]
pointer = receipt['artifact_pointer']  # "s3://bucket/result.json"
channel = receipt['artifact_location']  # "s3"
result = channel_client.fetch(channel, pointer)

# 6. Process and archive
process_result(result)
archive_inbox_receipt(receipt['receipt_id'])
```

### Delegated Planning

For complex tasks, use DeleGate:

```python
# 1. Request plan from DeleGate
plan = delegate.create_delegation_plan(
    intent="Analyze codebase and suggest optimizations",
    principal_ai="AgentName",
    caused_by_receipt_id=current_receipt_id
)
# Returns: plan (structured), receipt_id
# Receipt emitted: plan_created

# 2. Execute plan steps
for step in plan.steps:
    if step.step_type == "queue_execution":
        # Queue async work
        asyncgate.queue_task(
            task_type=step.worker_id,
            params=step.params,
            caused_by_receipt_id=plan.receipt_id  # Chain
        )
    
    elif step.step_type == "call_worker":
        # Direct call (fast)
        worker.call_tool(step.tool_name, step.params)
    
    elif step.step_type == "wait_for":
        # Check inbox for receipts
        # (handled in next bootstrap)
        break
    
    elif step.step_type == "aggregate":
        # Synthesize results
        combined = synthesize_results(step.aggregate_step_ids)
    
    elif step.step_type == "escalate":
        # Report upward (if in hierarchy)
        emit_escalation_receipt(step.report_summary)

# 3. Session ends, work continues
# Next session resumes from receipts
```

### Knowledge Promotion

Results don't automatically become knowledge. Agents decide what matters:

```python
# Fetch result from AsyncGate task
result = fetch_result_from_receipt(receipt)

# Synthesize insight
insight = synthesize_insight(result)

# Promote to permanent memory (explicit decision)
memory_store(
    observation=insight,
    domain="research",
    confidence=0.9,
    evidence=[receipt['receipt_id'], result.source]
)

# Archive receipt (work complete)
archive_inbox_receipt(receipt['receipt_id'])
```

---

<a name="flows"></a>
## 8. Complete Flows

### Flow 1: Simple Task (No Delegation)

**Scenario:** User asks agent to perform simple calculation

```
1. User → Agent: "Calculate 2+2"

Agent emits root receipt:
{
    "receipt_id": "R.20260104_100000_000.kee.user_calc_1",
    "event_type": "task_received",
    "recipient_ai": "kee",
    "requires_action": true
}

2. Agent performs calculation internally (no tier crossing, no receipt)

3. Agent → User: "4"

Agent emits completion:
{
    "receipt_id": "Complete.R.20260104_100000_000.kee.user_calc_1",
    "event_type": "task_complete",
    "recipient_ai": "external_system",
    "artifact_pointer": "inline:4"
}

MemoryGate auto-pairs, marks complete
```

**Receipt chain:**
```
R.20260104_100000_000.kee.user_calc_1 (root)
  └─ Complete.R.20260104_100000_000.kee.user_calc_1 (paired)
```

**Result:** 2 receipts, 1 pair, simple accountability

### Flow 2: Async Execution via AsyncGate

**Scenario:** Plan includes long-running task

```
1. User → Agent: "Index all documents"

Agent emits root:
{
    "receipt_id": "R.20260104_100000_000.kee.user_task_3",
    "event_type": "task_received",
    "requires_action": true
}

2. Agent creates plan (receipt emitted)

3. Agent executes plan step: queue async work

Agent → AsyncGate: queue_task(task_type="document_index", ...)

AsyncGate emits receipt:
{
    "receipt_id": "R.20260104_100002_750.asyncgate.task_xyz",
    "event_type": "task_queued",
    "recipient_ai": "kee",
    "caused_by_receipt_id": "R.20260104_100001_500.delegate.plan_abc",
    "artifact_pointer": "task_xyz",
    "artifact_location": "asyncgate_tasks",
    "requires_action": false,  // No action until completion
    "suggested_next_step": "Wait for completion receipt"
}

4. Agent session ends (work continues in background)

5. Worker leases task, executes

(Worker ↔ AsyncGate coordination, no receipts - internal)

6. Worker completes task

Worker → AsyncGate: complete_task(result_pointer="s3://bucket/index.json")

AsyncGate emits completion:
{
    "receipt_id": "Complete.R.20260104_100002_750.asyncgate.task_xyz",
    "event_type": "task_complete",
    "recipient_ai": "kee",
    "artifact_pointer": "s3://bucket/index.json",
    "artifact_location": "s3"
}

MemoryGate auto-pairs task_queued ↔ task_complete

7. Agent next session: bootstrap shows completion receipt

Agent fetches result from s3://bucket/index.json directly
Agent processes, completes user task

Agent emits final completion:
{
    "receipt_id": "Complete.R.20260104_100000_000.kee.user_task_3",
    "event_type": "task_complete",
    "recipient_ai": "external_system"
}
```

**Receipt chain:**
```
R.20260104_100000_000.kee.user_task_3 (root)
  ├─ R.20260104_100001_500.delegate.plan_abc (plan)
  │    └─ R.20260104_100002_750.asyncgate.task_xyz (queued)
  │         └─ Complete.R.20260104_100002_750.asyncgate.task_xyz (paired)
  └─ Complete.R.20260104_100000_000.kee.user_task_3 (paired)
```

**Result:** 5 receipts, 2 pairs, async work survived session reset

### Flow 3: Escalation to Higher Tier

**Scenario:** Domain DeleGate completes work, escalates to Principal

```
1. Principal → Domain DeleGate: "Research market trends"

Domain DeleGate emits receipt:
{
    "receipt_id": "R.20260104_100000_000.domain.principal_task_4",
    "event_type": "task_received",
    "recipient_ai": "domain_delegate_research",
    "requires_action": true
}

2. Domain DeleGate executes research (async work, receipts emitted)

3. Domain DeleGate completes internal work

Domain DeleGate emits completion to self:
{
    "receipt_id": "Complete.R.20260104_100000_000.domain.principal_task_4",
    "event_type": "task_complete",
    "recipient_ai": "domain_delegate_research"
}

4. Domain DeleGate escalates to Principal

Domain DeleGate creates NEW receipt for Principal:
{
    "receipt_id": "R.20260104_100510_000.domain.escalation_xyz",
    "event_type": "escalation",
    "recipient_ai": "principal",
    "summary": "Market research complete, decision required",
    "caused_by_receipt_id": "Complete.R.20260104_100000_000.domain.principal_task_4",
    "artifact_pointer": "s3://bucket/research_summary.json",
    "requires_action": true,
    "suggested_next_step": "Review findings and decide on market entry"
}

5. Principal reviews, makes decision, marks escalation complete

Principal emits:
{
    "receipt_id": "Complete.R.20260104_100510_000.domain.escalation_xyz",
    "event_type": "task_complete",
    "recipient_ai": "domain_delegate_research",
    "metadata": {"decision": "proceed", "rationale": "..."}
}
```

**Receipt chain:**
```
R.20260104_100000_000.domain.principal_task_4 (root)
  ├─ [async work receipts...]
  ├─ Complete.R.20260104_100000_000.domain.principal_task_4 (paired)
  └─ R.20260104_100510_000.domain.escalation_xyz (escalation)
       └─ Complete.R.20260104_100510_000.domain.escalation_xyz (paired)
```

**Key point:** Escalation creates NEW receipt with new owner (upward routing), not shared visibility.

---

<a name="use-cases"></a>
## 9. Use Cases

### Research Loop

```
1. Form hypothesis about consciousness theory
   → Receipt: task_received
2. DeleGate → literature review workers (async, hours)
   → Receipt: plan_created
   → Receipt: task_queued
3. Continue thinking about other aspects
4. Inbox: "Literature review complete (47 papers)"
   → Receipt: task_complete (auto-paired with task_queued)
5. Synthesize findings → update hypothesis
6. Store refined understanding in MemoryGate
7. Next iteration builds on this foundation
```

**Enabled by:** Persistent memory + non-blocking work + composable delegation + complete audit trail

### Code Development Loop

```
1. Design API specification
   → Receipt: task_received
2. DeleGate → code-analysis + security-scan workers (async)
   → Receipts: plan_created, task_queued (x2)
3. Work on documentation while code analysis runs
4. Inbox: "Code analysis complete" + "Security scan found 3 issues"
   → Receipts: task_complete (x2, both paired)
5. Review findings, update design
6. Store patterns learned in MemoryGate
7. Next API benefits from accumulated patterns
```

**Enabled by:** Worker specialization + receipt-based coordination + pattern extraction + provenance tracking

### Organization Coordination

```
Principal (CEO AI)
  ↓ Receipt: plan_created
General Manager DeleGate
  ├─→ Research Dept DeleGate
  │     → Receipts route to research dept inbox
  │     ├─→ Market research workers
  │     └─→ Competitive analysis workers
  │
  ├─→ Engineering Dept DeleGate
  │     → Receipts route to engineering dept inbox
  │     ├─→ Code quality workers
  │     └─→ Performance testing workers
  │
  └─→ Operations Dept DeleGate
        → Receipts route to operations dept inbox
        ├─→ Infrastructure monitoring workers
        └─→ Incident response workers

Each department:
- Runs its own cognitive loop
- Receives only relevant receipts (explicit routing)
- Escalates via new receipts to parent
- Builds domain-specific knowledge in MemoryGate
- Complete audit trail at every tier
```

**Enabled by:** Fractal delegation + uniform contracts + domain isolation + receipt ownership

---

<a name="implementation"></a>
## 10. Implementation Path

### Phase 1: Core Infrastructure

**1. MemoryGate MVP**
- Observations + patterns storage (PostgreSQL)
- Bootstrap + recall
- Semantic search (pgvector)
- Receipt table + validation
- Auto-pairing logic
- MCP tools interface

**2. AsyncGate MVP**
- Task queue + worker coordination (PostgreSQL)
- Email as first ResultChannel
- Receipt emission to MemoryGate
- FastAPI for workers, MCP for agents
- Lease/heartbeat/complete protocol

**3. DeleGate MVP**
- Worker discovery + registration
- Simple plan generation
- Receipt emission for plan_created
- Direct execution only (no nesting yet)

### Phase 2: Integration

**1. Receipt-Based Coordination**
- All boundary crossings emit receipts
- Bootstrap returns configuration + inbox
- Receipt chains enable audit
- Auto-pairing working across all components

**2. Async Delegation**
- DeleGate → AsyncGate routing for long work
- Plan execution with mixed direct/async steps
- Receipt tracking through entire flow

**3. Pattern Learning**
- Delegation trace storage
- Pattern extraction from successful decompositions
- Concept graph building

### Phase 3: Scale

**1. Additional ResultChannels**
- S3 for large payloads
- Blob storage
- Direct file access
- Channel selection logic

**2. DeleGate Nesting**
- Parent-child DeleGate relationships
- Domain-specific DeleGate instances
- Cross-department coordination
- Receipt routing per tier

**3. Advanced Memory**
- Concept graphs with relationships
- Document references with summaries
- Cross-domain pattern synthesis

**4. Receipt Analytics**
- Chain analysis for debugging
- Performance tracking
- Compliance reporting
- External audit API

### Phase 4: Production Hardening

**1. Monitoring & Observability**
- Prometheus metrics
- Grafana dashboards
- Alerting on key conditions
- Receipt chain visualization

**2. Security**
- Service token rotation
- Receipt encryption for sensitive metadata
- Access control per component
- External audit API authentication

**3. Scalability**
- Receipt archiving to cold storage
- Database sharding strategies
- AsyncGate worker pool scaling
- DeleGate instance management

**4. Developer Experience**
- Worker SDK (Python, TypeScript)
- Local development environment
- Integration testing framework
- Documentation site

---

<a name="principles"></a>
## 11. Design Principles

### 1. Workers Execute, DeleGates Delegate

**The Discriminator:** If it can create new tasks for other components, it's a DeleGate. If it can only execute what it's given, it's a Worker.

This is a hard architectural boundary. Workers cannot use AsyncGate to delegate to other workers. Only DeleGates decompose and route.

### 2. Separation Enables Independence

Remembering, working, and deciding are orthogonal concerns. Keep them separate so each can evolve independently. Add workers without touching memory. Add memory domains without touching delegation.

### 3. Epistemic Clarity Over Maximum Distribution

LegiVellum optimizes for epistemic clarity over maximum distribution; MemoryGate is intentionally centralized. A single source of truth prevents the coordination overhead, eventual consistency problems, and "who has the latest state?" confusion that plague distributed systems. This is not a weakness—it's a deliberate choice that makes the system understandable and trustworthy.

### 4. Topology Emerges, Architecture Doesn't Require It

**Critical insight:** LegiVellum does not prescribe deployment topology. "Clusters," "tiers," and "departments" are deployment convenience, not architectural requirements.

**The actual model:**
- Components identify themselves (`recipient_ai`)
- Components query MemoryGate for their work (polling)
- Components emit receipts for others to discover
- Database is the coordination substrate

**What this means:**
- You can run 1 DeleGate + 1 AsyncGate + 1 MemoryGate in a Docker Compose stack (convenient for development)
- You can run 10,000 identical `worker.codegen` processes across 1000 machines polling the same database (swarm mode)
- You can run heterogeneous components anywhere (laptop + AWS + GCP + Raspberry Pi) as long as they reach the same PostgreSQL
- You can organize components into logical "clusters" for operational convenience, but **the protocol doesn't enforce or require this**

**Why this matters:**
- No hardcoded topology in the architecture
- No service discovery needed (database IS the discovery)
- No cluster management overhead (Kubernetes optional, not required)
- Horizontal scaling is trivial (just start more workers with same `recipient_ai`)
- Migration across clouds is seamless (point workers at new database)

**Deployment is orthogonal to protocol.** The receipt ledger coordinates everything. Physical topology is an operational detail, not an architectural constraint.

### 5. Pointers Over Payloads

AsyncGate passes pointers through receipts, doesn't store them. MemoryGate stores receipts with pointers embedded, stores meaning, not raw results. This keeps each primitive focused.

### 6. Uniform Contracts Enable Fractals

DeleGates communicate with each other via the same contract they use with principals. No special cases. This makes nesting and composition trivial.

### 7. Receipts at Boundaries Only

Internal operations (thinking, internal synthesis) don't emit receipts. Only tier boundaries generate receipts. This prevents receipt spam while maintaining accountability.

### 8. Single Writer Principle

Only MemoryGate writes to receipt store. All other components POST receipts to MemoryGate. This prevents data corruption and enables schema validation.

### 9. Explicit Is Better Than Implicit

Promotion to permanent memory is intentional (agent decides). Result channels are explicit (email/s3/blob). Receipts explicitly chain (caused_by_receipt_id). No magic, no guessing.

### 10. Passivity Is Strength

MemoryGate doesn't volunteer state updates. AsyncGate doesn't interpret pointers. DeleGate doesn't execute plans. Each component does one thing and refuses to do others. This restraint is what makes the system stable.

### 11. Time Is Neutral

Because receipts persist, time stops being an enemy. Hours can pass. Sessions can reset. Systems can go idle. Nothing important is lost, because nothing important happens without leaving a receipt behind.

---

<a name="conclusion"></a>
## 12. Conclusion

We're done trying to build agents that remember everything, never block, and magically coordinate.

Instead, we're building the system that lets them forget, wait, and delegate—without falling apart.

### What LegiVellum Provides

**MemoryGate** — The permanent record
- Durable semantic memory across sessions
- Receipt storage (single source of truth)
- Bootstrap for session initialization
- Knowledge that accumulates instead of resetting

**AsyncGate** — The execution coordinator
- Task lifecycle management
- Worker coordination (lease/heartbeat/complete)
- Receipt emission with pointers
- Non-blocking async work

**DeleGate** — The pure planner
- Intent → Plan transformation
- Structured decomposition
- Fractal delegation
- No execution, no blocking

**Receipts** — The coordination protocol
- Proof of every meaningful action
- Chain from outcome to origin
- Auto-pairing for work completion
- One receipt, one owner

### What This Unlocks

**For Individual Agents:**
- Sessions build on prior sessions (no amnesia)
- Long tasks don't block thinking
- Results survive session resets
- Complete provenance from outcome to origin

**For Multi-Agent Systems:**
- Department-level coordination without chaos
- Clear ownership at every tier
- Explicit escalation pathways
- Fractal delegation that scales

**For Organizations:**
- AI systems that integrate with existing infrastructure
- Audit trails for compliance
- Predictable behavior under failure
- Infrastructure that can be trusted

### Why This Isn't Just Another Framework

This system doesn't try to produce a single, monolithic intelligence. It treats cognition as something that emerges from **coordination**, not cleverness.

The intelligence doesn't live in the dependencies. It lives in the **boundaries between them**.

Once those boundaries are enforced, recursion stops being a party trick and starts behaving like infrastructure.

### The Vellum Metaphor

LegiVellum — *legible vellum* — captures the essence:

Like the durable writing material used for contracts and important documents, LegiVellum provides:
- **Permanence:** Receipts are append-only, never erased
- **Legibility:** Complete audit trails make cognition transparent
- **Authority:** The permanent record that can be trusted

The system is a vellum for recursive cognition — where every important action leaves a mark that endures.

---

## Appendices

### A. Receipt Schema Reference

See `receipt_protocol.md` for complete specification.

### B. Component Specifications

- `memorygate_receipt_store.md` — MemoryGate implementation details
- `asyncgate_task_orchestration.txt` — AsyncGate specification
- `delegate_worker_orchestration.txt` — DeleGate specification

### C. Integration Examples

See section 7 (Integration Patterns) and section 8 (Complete Flows) in this document.

---

## References

**Core Documents:**
- `receipt_protocol.md` (~1,700 lines) — Universal coordination specification
- `memorygate_receipt_store.md` (850 lines) — MemoryGate implementation
- `trilogy_recursive_cognition_architecture.txt` (824 lines) — System architecture
- `asyncgate_task_orchestration.txt` (3,054 lines) — AsyncGate specification
- `delegate_worker_orchestration.txt` (2,128 lines) — DeleGate specification

**Total Specification:** ~8,500 lines across 5 documents

---

**LegiVellum**  
*The permanent record of recursive cognition*

**The trilogy is the scaffold.**  
**The AI is the mind that climbs it.**

---

*Whitepaper finalized: 2026-01-04*  
*Technomancy Laboratories*  
*Open design: memory, async work, and delegation—separated at last*
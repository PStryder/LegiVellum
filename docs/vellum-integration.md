# Vellum-LegiVellum Integration Guide

**Version**: 1.0.0
**Status**: Reference Documentation
**Last Updated**: 2026-01-25

---

## 1. Overview

Vellum is the specification language for LegiVellum. This document describes how Vellum integrates with LegiVellum's seven primitives and receipt protocol.

### 1.1 The Relationship

```
┌──────────────────────────────────────────────────────────────────┐
│                           VELLUM                                  │
│    Specification Language - What the AI agent intends to do      │
├──────────────────────────────────────────────────────────────────┤
│                         LEGIVELLUM                                │
│    Coordination Infrastructure - How the work gets done          │
│                                                                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │CogniGate│ │DeleGate │ │MemoryGt │ │AsyncGate│ │DepotGate│    │
│  │ Reason  │ │  Plan   │ │ Remember│ │ Execute │ │  Store  │    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘    │
│                          ↑                                       │
│                     RECEIPTS                                     │
│              Proof of Obligation Protocol                        │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Why Vellum + LegiVellum?

| Problem | Vellum Solution | LegiVellum Mechanism |
|---------|----------------|---------------------|
| Ambiguous intent | Explicit contracts | Receipts capture obligations |
| Capability sprawl | Declared `Can:` clauses | Escalation on missing capability |
| Lost context | Type-safe specifications | MemoryGate stores definitions |
| Blocking execution | Async-native operations | AsyncGate manages time |
| Untraceable outputs | Explicit `Emits:` clauses | Receipt provenance chains |

---

## 2. Mapping to LegiVellum Primitives

### 2.1 CogniGate Integration

CogniGate performs bounded cognition without side effects. Vellum supports this through:

**Pure Functions:**
```vellum
To analyze sentiment:
  Given:
    - text: String

  # No Can: clause = pure function, safe for CogniGate

  Returns: SentimentScore

  Implementation:
    # CogniGate can execute this directly
    Let words be text split by " "
    Let positive_count be the count of words where word is in positive_words
    Let negative_count be the count of words where word is in negative_words
    Return new SentimentScore with positive: positive_count, negative: negative_count
```

**CogniGate Constraints:**
- CogniGate can READ MemoryGate and receipts
- CogniGate can EMIT accepted receipts only
- CogniGate CANNOT create obligations or mint new tasks

In Vellum, this translates to:
```vellum
To cognigate_analyze:
  Can:
    - query memory          # Read from MemoryGate
    - emit receipts         # Only accepted phase

  Prohibits:
    - write to any resource
    - claim tasks
    - store artifacts
```

### 2.2 DeleGate Integration

DeleGate transforms unstructured intent into structured Plans. Vellum IS the structured plan format.

**Plan as Vellum Module:**
```vellum
# ProcessUserSignup
# Plan for handling new user registration

Version: 1.0.0
LegiVellum: ^1.1.0

---

Define record SignupPlan:
  steps: Collection<PlanStep>
  dependencies: Map<StepId, Collection<StepId>>
  timeout: Duration

  Invariants:
    steps is not empty
    all step in steps have step.id exists in dependencies.keys

Define record PlanStep:
  id: StepId
  task_type: String
  task_body: String
  expected_outcome: OutcomeKind
  can_parallel: Boolean

---

public To create signup plan:
  Given:
    - user_data: UserRegistration

  Can:
    - emit receipts    # DeleGate authority to create obligations

  Returns: SignupPlan

  Emits:
    - accepted receipt for each step

  Implementation:
    Let validate_step be new PlanStep with:
      - id: "validate"
      - task_type: "validation"
      - task_body: "Validate user data: " followed by user_data.email
      - expected_outcome: response_text
      - can_parallel: false

    Let create_step be new PlanStep with:
      - id: "create"
      - task_type: "persistence"
      - task_body: "Create user record"
      - expected_outcome: artifact_pointer
      - can_parallel: false

    Let notify_step be new PlanStep with:
      - id: "notify"
      - task_type: "notification"
      - task_body: "Send welcome email"
      - expected_outcome: none
      - can_parallel: true

    # Emit accepted receipts for each step
    accept task validate_step
    accept task create_step
    accept task notify_step

    Return new SignupPlan with:
      - steps: [validate_step, create_step, notify_step]
      - dependencies: {"create": ["validate"], "notify": ["create"]}
      - timeout: 5 minutes
```

### 2.3 MemoryGate Integration

MemoryGate stores durable semantic memory. Vellum definitions become storable concepts.

**Storing Vellum Definitions:**
```vellum
To store domain concept:
  Given:
    - name: String
    - definition: VellumDefinition
    - confidence: Decimal

  Can:
    - write to memory

  Returns: Result<ConceptId, MemoryError>

  Implementation:
    Let concept be new Concept with:
      - name: name
      - concept_type: "vellum_definition"
      - description: definition.source_text
      - domain: definition.module_name

    Save concept to memory
    Return success(concept.id)
```

**Querying Vellum Patterns:**
```vellum
To find relevant patterns:
  Given:
    - query: String
    - min_confidence: Decimal

  Can:
    - query memory

  Returns: Collection<Pattern>

  Implementation:
    Let results be search memory for query with limit 10
    Return results where confidence is at least min_confidence
```

### 2.4 AsyncGate Integration

AsyncGate manages time-decoupled execution. Vellum procedures map to AsyncGate tasks.

**Task Submission:**
```vellum
To submit async task:
  Given:
    - procedure: VellumProcedure
    - inputs: Map<String, Any>
    - timeout: Duration

  Can:
    - emit receipts
    - async call AsyncGate.submit

  Returns: Future<TaskId>

  Emits:
    - accepted receipt immediately

  Implementation:
    Let task_body be serialize procedure with inputs

    Let receipt be accept task new TaskDefinition with:
      - task_type: procedure.name
      - task_body: task_body
      - expected_outcome: infer_outcome_kind from procedure.returns
      - timeout: timeout

    Return receipt.task_id
```

**Lease-Aware Execution:**
```vellum
To execute with lease:
  Given:
    - task_id: ULID
    - worker_id: Identifier

  Can:
    - claim tasks
    - emit receipts
    - timeout after 5 minutes

  Returns: Future<Result<TaskResult, ExecutionError>>

  Implementation:
    Let lease_result be claim task task_id

    if lease_result failed then
      Return failure(LeaseError with "Could not acquire lease")

    Let lease be lease_result.value

    # Heartbeat loop runs in background
    spawn heartbeat_loop with lease

    Try:
      Let result be await execute task task_id
      complete task task_id with success(result)
      Return success(result)
    Catch TimeoutError:
      escalate task task_id to retry_handler because "Execution timeout"
      Return failure(TimeoutError)
    Catch _ as err:
      escalate task task_id to error_handler because err.message
      Return failure(err)

To heartbeat_loop:
  Given:
    - lease: Lease

  Can:
    - async call AsyncGate.heartbeat

  Implementation:
    repeat while lease is not expired:
      await sleep for (lease.duration divided by 3)
      renew lease lease
```

### 2.5 DepotGate Integration

DepotGate manages artifact storage. Vellum artifacts map to DepotGate resources.

**Storing Artifacts:**
```vellum
To store computation result:
  Given:
    - content: Bytes
    - mime_type: String
    - task_id: ULID

  Can:
    - store artifacts

  Returns: Result<Artifact, DepotError>

  Implementation:
    Let artifact be store artifact content as mime_type

    Return success(new Artifact with:
      - pointer: artifact.pointer
      - location: artifact.location
      - mime_type: mime_type
      - task_id: task_id
      - created_at: now
    )
```

**Artifact References in Receipts:**
```vellum
To complete with artifact:
  Given:
    - task_id: ULID
    - artifact: Artifact

  Can:
    - emit receipts

  Emits:
    - complete receipt with artifact_pointer outcome

  Implementation:
    complete task task_id with success(new Outcome with:
      - kind: artifact_pointer
      - artifact_pointer: artifact.pointer
      - artifact_location: artifact.location
      - artifact_mime: artifact.mime_type
    )
```

### 2.6 MetaGate Integration

MetaGate handles bootstrap and lifecycle. Vellum modules register through MetaGate.

**Module Registration:**
```vellum
To register vellum module:
  Given:
    - module: VellumModule

  Can:
    - call MetaGate.register

  Returns: Result<ModuleId, RegistrationError>

  Implementation:
    Let registration be new ComponentRegistration with:
      - name: module.name
      - version: module.version
      - type: "vellum_module"
      - capabilities: module.declared_capabilities
      - dependencies: module.requires

    Return await MetaGate.register with registration
```

---

## 3. Receipt Protocol Mapping

### 3.1 Contract → Receipt Lifecycle

```
VELLUM PROCEDURE                    RECEIPT PROTOCOL
─────────────────                   ────────────────

Given: (parameters)        ──────►  task_body, inputs
Requires: (preconditions)  ──────►  Validated before accepted

         ┌─────────────────────────────────────────┐
         │            ACCEPTED RECEIPT             │
         │  phase: accepted                        │
         │  status: NA                             │
         │  task_summary: procedure.name           │
         │  expected_outcome_kind: from Returns    │
         └─────────────────────────────────────────┘
                          │
                          ▼
Implementation:           │  Worker holds lease
  statements              │  Heartbeats renew
                          │
                          ▼
         ┌─────────────────────────────────────────┐
Ensures: │            COMPLETE RECEIPT             │
(post-   │  phase: complete                        │
 conds)  │  status: success | failure | canceled   │
         │  outcome_kind: from actual result       │
         │  completed_at: timestamp                │
         └─────────────────────────────────────────┘
                          │
                          │ (on error)
                          ▼
         ┌─────────────────────────────────────────┐
Can:     │            ESCALATE RECEIPT             │
(missing │  phase: escalate                        │
 caps)   │  status: NA                             │
         │  escalation_class: from error type      │
         │  escalation_to: capable handler         │
         └─────────────────────────────────────────┘
```

### 3.2 Result Type → Receipt Outcome

```vellum
# Vellum Result types map to receipt outcomes

Returns: Result<Order, OrderError>

# On success(order):
complete receipt:
  status: success
  outcome_kind: response_text | artifact_pointer
  outcome_text: serialized order (if response_text)
  artifact_pointer: order location (if artifact_pointer)

# On failure(OrderError.PaymentFailed):
escalate receipt:
  escalation_class: capability  # Payment capability missing
  escalation_reason: "Payment failed: " + error.message
  escalation_to: payment_handler

# On failure(OrderError.Timeout):
escalate receipt:
  escalation_class: policy  # Timeout policy exceeded
  escalation_reason: "Operation timed out"
  escalation_to: retry_handler
```

### 3.3 Capability Violations → Escalation

```vellum
To process payment:
  Can:
    - async call PaymentGateway.charge    # REQUIRED
    - timeout after 30 seconds

  # If PaymentGateway.charge is unavailable:
  # → escalate with class: capability
  # → escalation_to: payment_capable_handler

  # If timeout exceeded:
  # → escalate with class: policy
  # → escalation_to: retry_handler
```

---

## 4. Implementation Patterns

### 4.1 Pattern: Task Worker

```vellum
# Standard pattern for AsyncGate worker

To worker_loop:
  Given:
    - principal: Principal
    - worker_id: Identifier

  Can:
    - claim tasks
    - emit receipts
    - query memory
    - log messages

  Implementation:
    repeat while true:
      Let inbox be the inbox for principal
      Let ready_tasks be inbox where phase is accepted

      if ready_tasks is empty then
        await sleep for 1 second
        continue

      for each task in ready_tasks:
        Let result be await process_task with task, worker_id

        if result failed then
          Log warning: "Task failed: " followed by task.task_id
```

### 4.2 Pattern: Delegation Chain

```vellum
# Pattern for DeleGate creating sub-tasks

To delegate_complex_task:
  Given:
    - parent_task: Receipt
    - subtasks: Collection<TaskDefinition>

  Can:
    - emit receipts

  Emits:
    - accepted receipt for each subtask

  Implementation:
    for each subtask in subtasks:
      Let receipt be accept task subtask with:
        - parent_task_id: parent_task.task_id
        - caused_by_receipt_id: parent_task.receipt_id

      Log info: "Delegated subtask: " followed by receipt.task_id

    # Parent task waits for all subtasks
    Let completion_task be accept task new TaskDefinition with:
      - task_type: "aggregation"
      - task_body: "Wait for subtasks and aggregate"
      - parent_task_id: parent_task.task_id
```

### 4.3 Pattern: Retry with Backoff

```vellum
To retry_with_backoff <T, E>:
  Given:
    - operation: Task<T, E>
    - max_attempts: Integer
    - base_delay: Duration

  Can:
    - log messages
    - retry up to max_attempts times

  Returns: Future<Result<T, E>>

  Implementation:
    Let attempts be 0
    Let delay be base_delay

    repeat while attempts is less than max_attempts:
      Let result be await operation

      if result succeeded then
        Return result

      Set attempts to attempts plus 1
      Log warning: "Attempt " followed by attempts followed by " failed, retrying in " followed by delay

      await sleep for delay
      Set delay to delay times 2  # Exponential backoff

    Return failure(RetryExhausted with max_attempts)
```

### 4.4 Pattern: Capability Check

```vellum
To check_and_execute:
  Given:
    - task: Receipt
    - required_caps: Collection<Capability>
    - available_caps: Collection<Capability>

  Can:
    - emit receipts

  Returns: Result<Outcome, EscalationNeeded>

  Implementation:
    Let missing be required_caps where cap is not in available_caps

    if missing is not empty then
      Let first_missing be the first cap in missing

      escalate task task.task_id to capability_holder because
        "Missing capability: " followed by first_missing.name

      Return failure(EscalationNeeded with:
        - class: capability
        - missing: missing
      )

    # All capabilities present, execute
    Let result be await execute task task
    Return success(result)
```

---

## 5. Translation to Executable Code

### 5.1 Python Target

```vellum
# Vellum source
To process order:
  Given:
    - user_id: Identifier
    - items: Collection<LineItem>

  Can:
    - emit receipts
    - async call PaymentGateway.charge

  Returns: Future<Result<Order, OrderError>>
```

```python
# Generated Python
from legivellum import Receipt, emit_accepted, emit_complete, emit_escalate
from legivellum.types import Result, success, failure
from typing import List
import asyncio

async def process_order(
    user_id: str,
    items: List[LineItem],
    # Capability injection
    receipt_emitter: ReceiptEmitter,
    payment_gateway: PaymentGateway,
) -> Result[Order, OrderError]:
    """
    Vellum-generated procedure.

    Can:
      - emit receipts
      - async call PaymentGateway.charge
    """
    # Implementation follows...
```

### 5.2 Rust Target

```rust
// Generated Rust
use legivellum::{Receipt, Result, EmitReceipts, AsyncCall};

#[vellum(
    can = ["emit_receipts", "async_call(PaymentGateway.charge)"]
)]
async fn process_order(
    user_id: Identifier,
    items: Vec<LineItem>,
    // Capability injection
    receipt_emitter: impl EmitReceipts,
    payment_gateway: impl AsyncCall<PaymentGateway>,
) -> Result<Order, OrderError> {
    // Implementation follows...
}
```

---

## 6. Best Practices

### 6.1 Capability Minimization

Always declare the minimum capabilities needed:

```vellum
# BAD: Over-broad capabilities
Can:
  - access network
  - access filesystem
  - emit receipts

# GOOD: Specific capabilities
Can:
  - async call PaymentGateway.charge
  - write to orders
  - emit receipts
```

### 6.2 Explicit Escalation Paths

Define where work goes when it can't be completed:

```vellum
# Implicit escalation (BAD)
To risky_operation:
  # What happens on failure? Unclear.

# Explicit escalation (GOOD)
To risky_operation:
  Emits:
    - escalate to fallback_handler on CapabilityError
    - escalate to retry_handler on TimeoutError
    - escalate to human_review on UnknownError
```

### 6.3 Receipt Provenance

Always maintain causality chains:

```vellum
# When creating sub-tasks
accept task subtask with:
  - parent_task_id: parent.task_id          # Task hierarchy
  - caused_by_receipt_id: parent.receipt_id  # Receipt causality
```

### 6.4 Testable Contracts

Write contracts that can be verified:

```vellum
# Untestable (BAD)
Ensures:
  - result is correct

# Testable (GOOD)
Ensures:
  - if result succeeded then result.value.total is at least 0
  - if result succeeded then result.value.items is not empty
  - if result failed then no receipts were emitted with phase complete
```

---

## 7. Migration Guide

### 7.1 From Raw Python to Vellum

**Before:**
```python
async def process_task(task_id: str) -> dict:
    # Implicit capabilities, no contracts
    result = await payment.charge(amount)
    await db.save(order)
    return {"status": "success"}
```

**After:**
```vellum
To process task:
  Given:
    - task_id: ULID

  Requires:
    - task_id exists in inbox

  Can:
    - async call Payment.charge
    - write to orders
    - emit receipts

  Returns: Result<Order, ProcessingError>

  Ensures:
    - if result succeeded then order exists in orders
    - if result succeeded then complete receipt emitted

  Implementation:
    # Explicit, traceable, type-safe
```

### 7.2 From Existing LegiVellum to Vellum

Existing LegiVellum components can adopt Vellum incrementally:

1. **Define types** in `.vellum` files
2. **Write procedures** with explicit contracts
3. **Generate code** for your target language
4. **Replace** existing implementations gradually

---

## Appendix: Quick Reference

### Vellum → LegiVellum Mapping

| Vellum Construct | LegiVellum Component | Receipt Field |
|-----------------|---------------------|---------------|
| `Module:` | MetaGate registration | - |
| `Given:` | - | task_body, inputs |
| `Requires:` | Pre-acceptance validation | - |
| `Can:` | Capability check | escalation_class |
| `Prohibits:` | Capability denial | escalation_class |
| `Returns:` | - | expected_outcome_kind |
| `Ensures:` | Pre-completion validation | - |
| `Emits:` | Receipt emission | phase |
| `accept task` | DeleGate authority | phase: accepted |
| `complete task` | Resolution | phase: complete |
| `escalate task` | Responsibility transfer | phase: escalate |
| `claim task` | AsyncGate lease | lease_id |
| `store artifact` | DepotGate write | artifact_pointer |
| `query memory` | MemoryGate read | - |

---

*End of Integration Guide*

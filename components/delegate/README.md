# DeleGate

**The Pure Planner**

DeleGate transforms intent into structured plans and delegates execution without blocking.

## Purpose

- Convert unstructured intent into actionable plans
- Decompose complex tasks into subtasks
- Route work to appropriate workers via AsyncGate
- Enable fractal delegation across tiers

## Responsibilities

- **Intent → Plan:** Transform natural language requests into structured task plans
- **Plan Validation:** Ensure plans are well-formed and executable
- **Delegation:** Submit tasks to AsyncGate for execution
- **Receipt Emission:**
  - Emit `accepted` receipt on plan creation
  - Emit `complete` receipt when plan resolves
  - Emit `escalate` receipt when plan cannot be executed
- **Fractal Coordination:** DeleGates can delegate to other DeleGates

## What DeleGate Does NOT Do

- Execute tasks directly (delegates to AsyncGate)
- Wait for results (non-blocking)
- Manage worker pools (AsyncGate's job)
- Store state (posts receipts to MemoryGate)

## Architecture Notes

DeleGates use the same contract to communicate with each other as they use with principals. No special cases. This makes nesting and composition trivial.

Only DeleGates can create new tasks for other components. Workers cannot use AsyncGate to delegate—this is the architectural discriminator that prevents chaotic fan-out.

## Key Principle

> Workers execute. DeleGates delegate.

---

See `/spec/delegate_worker_orchestration.txt` for detailed specification.

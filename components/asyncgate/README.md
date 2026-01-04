# AsyncGate

**The Execution Coordinator**

AsyncGate manages task lifecycle, worker coordination, and non-blocking async work execution.

## Purpose

- Coordinate work execution without blocking cognitive cycles
- Manage worker leases and heartbeats
- Emit receipts with artifact pointers on completion
- Enable long-running tasks to execute while agents continue thinking

## Responsibilities

- **Task Queue:** Accept task submissions from DeleGates
- **Worker Coordination:** Lease assignment, heartbeat monitoring, orphan detection
- **Lifecycle Management:** Track queued → leased → complete/failed states
- **Receipt Emission:** 
  - Emit `accepted` receipt on task queue
  - Emit `complete` receipt with artifact_pointer on finish
  - Emit `escalate` receipt on worker failure
- **Retry Logic:** Automatic requeue on lease expiry, max retry handling

## What AsyncGate Does NOT Do

- Interpret artifact contents (passes opaque pointers)
- Make planning decisions (DeleGate's job)
- Store receipts (posts to MemoryGate)
- Determine what work to create (only executes delegated tasks)

## Architecture Notes

AsyncGate treats time as neutral. Hours can pass, workers can restart, systems can go idle—nothing important is lost because every meaningful event leaves a receipt.

## Key Principle

> AsyncGate coordinates execution, not cognition.

---

See `/spec/asyncgate_task_orchestration.txt` for detailed specification.

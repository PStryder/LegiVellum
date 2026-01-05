"""
DeleGate Plan Generation

Simple rule-based plan generation for MVP.
In production, this could use LLM-based planning.
"""
from typing import Any
import re

from models import (
    Plan,
    PlanStep,
    PlanRequest,
    StepType,
    generate_plan_id,
    generate_step_id,
)


# =============================================================================
# Intent Analysis
# =============================================================================

# Simple keyword-based intent detection
INTENT_PATTERNS = {
    # Code-related intents
    r"generate|create|write|implement": "code.generate",
    r"review|check|analyze code": "code.review",
    r"refactor|improve|optimize code": "code.refactor",

    # Data-related intents
    r"analyze|examine|investigate data": "data.analyze",
    r"transform|convert|process data": "data.transform",

    # Text-related intents
    r"summarize|summary|tldr": "text.summarize",
    r"translate|translation": "text.translate",

    # Search/research
    r"search|find|lookup|research": "search",

    # Image-related
    r"generate image|create image|draw": "image.generate",
}


def detect_intent_type(intent: str) -> str:
    """Detect the primary task type from intent"""
    intent_lower = intent.lower()

    for pattern, task_type in INTENT_PATTERNS.items():
        if re.search(pattern, intent_lower):
            return task_type

    return "generic"


def estimate_complexity(intent: str, context: dict) -> str:
    """Estimate task complexity: simple, medium, complex"""
    # Simple heuristics for MVP
    intent_lower = intent.lower()

    complex_indicators = [
        "multiple", "several", "all", "entire", "complete",
        "analyze", "research", "comprehensive", "full",
    ]

    simple_indicators = [
        "single", "one", "simple", "quick", "just",
    ]

    complex_score = sum(1 for i in complex_indicators if i in intent_lower)
    simple_score = sum(1 for i in simple_indicators if i in intent_lower)

    if complex_score > simple_score + 1:
        return "complex"
    elif simple_score > complex_score:
        return "simple"
    else:
        return "medium"


# =============================================================================
# Plan Generation
# =============================================================================

def create_plan(request: PlanRequest) -> Plan:
    """
    Create a delegation plan from an intent.

    MVP: Simple rule-based planning.
    Production: Could integrate LLM for complex planning.
    """
    intent = request.intent
    principal = request.principal_ai
    context = request.context

    # Detect intent type and complexity
    task_type = detect_intent_type(intent)
    complexity = estimate_complexity(intent, context)

    # Build plan based on complexity
    if complexity == "simple":
        return create_simple_plan(request, task_type)
    elif complexity == "medium":
        return create_medium_plan(request, task_type)
    else:
        return create_complex_plan(request, task_type)


def create_simple_plan(request: PlanRequest, task_type: str) -> Plan:
    """Create a simple single-step plan"""
    steps = [
        PlanStep(
            step_id=generate_step_id(),
            step_type=StepType.QUEUE_EXECUTION,
            description=f"Execute {task_type} task",
            task_type=task_type,
            params={"intent": request.intent, **request.context},
            estimated_runtime_seconds=60,
        ),
        PlanStep(
            step_id=generate_step_id(),
            step_type=StepType.ESCALATE,
            description="Report completion",
            report_summary=f"Completed: {request.intent}",
            recommendation="Review results",
        ),
    ]

    # Set dependencies
    steps[1].depends_on = [steps[0].step_id]

    return Plan(
        plan_id=generate_plan_id(),
        principal_ai=request.principal_ai,
        intent=request.intent,
        confidence=0.9,
        steps=steps,
        estimated_total_runtime_seconds=90,
    )


def create_medium_plan(request: PlanRequest, task_type: str) -> Plan:
    """Create a medium complexity plan with async work + aggregation"""
    step1_id = generate_step_id()
    step2_id = generate_step_id()
    step3_id = generate_step_id()
    step4_id = generate_step_id()

    steps = [
        PlanStep(
            step_id=step1_id,
            step_type=StepType.QUEUE_EXECUTION,
            description=f"Execute primary {task_type} task",
            task_type=task_type,
            params={"intent": request.intent, **request.context},
            estimated_runtime_seconds=120,
        ),
        PlanStep(
            step_id=step2_id,
            step_type=StepType.WAIT_FOR,
            description="Wait for primary task completion",
            wait_for_step_ids=[step1_id],
        ),
        PlanStep(
            step_id=step3_id,
            step_type=StepType.AGGREGATE,
            description="Synthesize results",
            aggregate_step_ids=[step1_id],
            synthesis_instructions="Combine and summarize the results",
            executor="principal",
            depends_on=[step2_id],
        ),
        PlanStep(
            step_id=step4_id,
            step_type=StepType.ESCALATE,
            description="Report completion with synthesis",
            report_summary=f"Completed: {request.intent}",
            recommendation="Review synthesized results",
            depends_on=[step3_id],
        ),
    ]

    return Plan(
        plan_id=generate_plan_id(),
        principal_ai=request.principal_ai,
        intent=request.intent,
        confidence=0.8,
        steps=steps,
        estimated_total_runtime_seconds=180,
    )


def create_complex_plan(request: PlanRequest, task_type: str) -> Plan:
    """Create a complex plan with parallel tasks + aggregation"""
    # For complex plans, split into subtasks
    subtasks = split_into_subtasks(request.intent, task_type)

    steps = []
    subtask_step_ids = []

    # Create parallel execution steps
    for i, subtask in enumerate(subtasks):
        step_id = generate_step_id()
        subtask_step_ids.append(step_id)

        steps.append(PlanStep(
            step_id=step_id,
            step_type=StepType.QUEUE_EXECUTION,
            description=f"Execute subtask {i+1}: {subtask['description']}",
            task_type=subtask["task_type"],
            params=subtask["params"],
            estimated_runtime_seconds=subtask.get("estimated_time", 120),
        ))

    # Wait for all subtasks
    wait_step_id = generate_step_id()
    steps.append(PlanStep(
        step_id=wait_step_id,
        step_type=StepType.WAIT_FOR,
        description="Wait for all subtasks to complete",
        wait_for_step_ids=subtask_step_ids,
    ))

    # Aggregate results
    aggregate_step_id = generate_step_id()
    steps.append(PlanStep(
        step_id=aggregate_step_id,
        step_type=StepType.AGGREGATE,
        description="Synthesize all subtask results",
        aggregate_step_ids=subtask_step_ids,
        synthesis_instructions="Combine results from all subtasks into a coherent output",
        executor="principal",
        depends_on=[wait_step_id],
    ))

    # Final escalation
    steps.append(PlanStep(
        step_id=generate_step_id(),
        step_type=StepType.ESCALATE,
        description="Report completion with full synthesis",
        report_summary=f"Completed complex task: {request.intent}",
        recommendation="Review comprehensive results",
        depends_on=[aggregate_step_id],
    ))

    total_time = sum(s.estimated_runtime_seconds or 0 for s in steps if s.step_type == StepType.QUEUE_EXECUTION)

    return Plan(
        plan_id=generate_plan_id(),
        principal_ai=request.principal_ai,
        intent=request.intent,
        confidence=0.7,  # Lower confidence for complex plans
        steps=steps,
        estimated_total_runtime_seconds=total_time + 60,  # Add overhead
        notes="Complex plan with parallel execution",
    )


def split_into_subtasks(intent: str, task_type: str) -> list[dict[str, Any]]:
    """
    Split a complex intent into subtasks.

    MVP: Simple heuristics.
    Production: LLM-based decomposition.
    """
    intent_lower = intent.lower()

    # Check for explicit "and" or comma-separated items
    if " and " in intent_lower or "," in intent:
        parts = re.split(r",| and ", intent, flags=re.IGNORECASE)
        subtasks = []
        for i, part in enumerate(parts):
            part = part.strip()
            if part:
                subtasks.append({
                    "description": part,
                    "task_type": detect_intent_type(part) or task_type,
                    "params": {"subtask": part, "part_number": i + 1},
                    "estimated_time": 120,
                })
        return subtasks if subtasks else _default_subtasks(intent, task_type)

    # Check for "all" or "multiple" indicators
    if any(word in intent_lower for word in ["all", "multiple", "several", "every"]):
        # Create analyze + synthesize subtasks
        return [
            {
                "description": f"Gather data for: {intent}",
                "task_type": "search" if "search" in intent_lower else task_type,
                "params": {"phase": "gather", "intent": intent},
                "estimated_time": 180,
            },
            {
                "description": f"Analyze gathered data",
                "task_type": "data.analyze",
                "params": {"phase": "analyze", "intent": intent},
                "estimated_time": 120,
            },
            {
                "description": f"Generate final output",
                "task_type": task_type,
                "params": {"phase": "generate", "intent": intent},
                "estimated_time": 120,
            },
        ]

    return _default_subtasks(intent, task_type)


def _default_subtasks(intent: str, task_type: str) -> list[dict[str, Any]]:
    """Default subtask split for unrecognized patterns"""
    return [
        {
            "description": f"Primary task: {intent}",
            "task_type": task_type,
            "params": {"intent": intent},
            "estimated_time": 180,
        },
        {
            "description": "Verify and validate results",
            "task_type": "generic",
            "params": {"phase": "verify", "intent": intent},
            "estimated_time": 60,
        },
    ]

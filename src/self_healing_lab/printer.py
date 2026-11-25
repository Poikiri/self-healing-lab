"""Prints what is happening during a run."""

from self_healing_lab.models import (
    Fault,
    PlanOutcome,
    PlanResult,
    RecoveryPlan,
    RunResult,
    Step,
)
from self_healing_lab.report import FAULT_TEXT, describe_step


def print_step(number: int, step: Step) -> None:
    """Print the step about to run.

    Args:
        number: The step's position in the protocol.
        step: The step about to run.

    Returns:
        None.
    """
    print(f"Step {number}: {describe_step(step)}")


def print_fault(fault: Fault) -> None:
    """Print what went wrong.

    Args:
        fault: What went wrong.

    Returns:
        None.
    """
    print(f"  FAILED: {FAULT_TEXT[fault.type]}")


def print_plan(plan: RecoveryPlan) -> None:
    """Print the plan the AI suggested.

    Args:
        plan: The suggested plan.

    Returns:
        None.
    """
    print(f"  AI suggests: {', then '.join(action.name for action in plan.actions)}")


def print_agent_error(message: str) -> None:
    """Print why the AI gave no plan.

    Args:
        message: What went wrong.

    Returns:
        None.
    """
    print(f"  AI ERROR: {message}")


def print_check(problems: list[str]) -> None:
    """Print whether the safety checker allowed the plan.

    Args:
        problems: The problems found.

    Returns:
        None.
    """
    if not problems:
        print("  Safety check: accepted")
        return
    print("  Safety check: REJECTED")
    for problem in problems:
        print(f"    - {problem}")


def print_plan_result(result: PlanResult) -> None:
    """Print how carrying out the plan ended.

    Args:
        result: How the plan ended.

    Returns:
        None.
    """
    if result.outcome == PlanOutcome.RECOVERED:
        print("  Fix worked, continuing")
    if result.fault is not None:
        print(f"  Fix failed: {FAULT_TEXT[result.fault.type]}")


def print_alert() -> None:
    """Print that a human is needed.

    Args:
        None.

    Returns:
        None.
    """
    print("  PAUSED: a human needs to help")


def print_summary(result: RunResult, total_steps: int) -> None:
    """Print a summary of the run.

    Args:
        result: What happened.
        total_steps: How many steps the protocol has.

    Returns:
        None.
    """
    fixed = sum(record.is_fixed() for record in result.recoveries)
    print()
    print(f"Result: {'completed' if result.completed else 'paused'}")
    print(f"Steps run: {len(result.steps_run)} of {total_steps}")
    print(f"Failures: {len(result.recoveries)}, fixed: {fixed}")

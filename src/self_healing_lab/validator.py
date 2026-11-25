"""Checks whether a recovery plan is allowed. Plain rules, no AI."""

from self_healing_lab import config
from self_healing_lab.models import (
    ActionName,
    DeckState,
    Fault,
    FaultType,
    RecoveryAction,
    RecoveryPlan,
)

RETRY = ActionName.RETRY_STEP.value
NEW_TIP = ActionName.GET_NEW_TIP.value
REASPIRATE = ActionName.REASPIRATE.value
PAUSE = ActionName.PAUSE_AND_ALERT.value

# Actions that redo the failed step. Nothing can redo a step with a missing plate.
REDO_ACTIONS: dict[FaultType, list[str]] = {
    FaultType.TIP_PICKUP_FAILED: [RETRY, NEW_TIP],
    FaultType.ASPIRATION_FAILED: [RETRY, REASPIRATE],
    FaultType.PLATE_MISSING: [],
}

# Actions allowed before the last one.
PREPARE_ACTIONS: dict[FaultType, list[str]] = {
    FaultType.TIP_PICKUP_FAILED: [],
    FaultType.ASPIRATION_FAILED: [NEW_TIP],
    FaultType.PLATE_MISSING: [],
}


def validate_plan(
    plan: RecoveryPlan, fault: Fault, deck: DeckState, retries_used: int
) -> list[str]:
    """Check a plan against every rule.

    Args:
        plan: The plan to check.
        fault: The failure the plan should fix.
        deck: The deck right now.
        retries_used: How many times the failed step was already retried.

    Returns:
        The problems found. An empty list means the plan is allowed.
    """
    return (
        check_names(plan)
        + check_length(plan)
        + check_order(plan, fault)
        + check_retries(plan, fault, retries_used)
        + check_volumes(plan, fault, deck)
        + check_heights(plan)
    )


def check_names(plan: RecoveryPlan) -> list[str]:
    """Check that every action is a known one.

    Args:
        plan: The plan to check.

    Returns:
        The problems found.
    """
    known = [name.value for name in ActionName]
    return [f"Unknown action: {a.name}" for a in plan.actions if a.name not in known]


def check_length(plan: RecoveryPlan) -> list[str]:
    """Check that the plan is not empty or too long.

    Args:
        plan: The plan to check.

    Returns:
        The problems found.
    """
    if 1 <= len(plan.actions) <= config.MAX_PLAN_LENGTH:
        return []
    return [f"A plan needs 1 to {config.MAX_PLAN_LENGTH} actions, not {len(plan.actions)}"]


def check_order(plan: RecoveryPlan, fault: Fault) -> list[str]:
    """Check that the plan ends by redoing the failed step or pausing.

    Args:
        plan: The plan to check.
        fault: The failure the plan should fix.

    Returns:
        The problems found.
    """
    names = [action.name for action in plan.actions]
    allowed_last = REDO_ACTIONS[fault.type] + [PAUSE]
    allowed_before = PREPARE_ACTIONS[fault.type]
    problems = [
        f"{name} can't come before the last action for {fault.type.value}"
        for name in names[:-1]
        if name not in allowed_before
    ]
    if names and names[-1] not in allowed_last:
        problems.append(f"{names[-1]} can't be the last action for {fault.type.value}")
    return problems


def check_retries(plan: RecoveryPlan, fault: Fault, retries_used: int) -> list[str]:
    """Check that the failed step is not retried too often.

    Args:
        plan: The plan to check.
        fault: The failure the plan should fix.
        retries_used: How many times the failed step was already retried.

    Returns:
        The problems found.
    """
    redo_actions = REDO_ACTIONS[fault.type]
    retries = retries_used + sum(action.name in redo_actions for action in plan.actions)
    if retries <= config.MAX_RETRIES_PER_STEP:
        return []
    return [f"The step can be retried at most {config.MAX_RETRIES_PER_STEP} time(s)"]


def check_volumes(plan: RecoveryPlan, fault: Fault, deck: DeckState) -> list[str]:
    """Check that every redraw uses a possible volume.

    Args:
        plan: The plan to check.
        fault: The failure the plan should fix.
        deck: The deck right now.

    Returns:
        The problems found.
    """
    if fault.type != FaultType.ASPIRATION_FAILED:
        return []
    available = deck.volume_for(fault.step)
    lowest = fault.step.volume_ul
    highest = min(config.TIP_CAPACITY_UL, available)
    return [
        f"Volume must be {lowest} to {highest} µL, not {action.volume_ul}"
        for action in redraws(plan)
        if action.volume_ul is not None and not lowest <= action.volume_ul <= highest
    ]


def check_heights(plan: RecoveryPlan) -> list[str]:
    """Check that every redraw uses a possible height.

    Args:
        plan: The plan to check.

    Returns:
        The problems found.
    """
    lowest = config.MIN_HEIGHT_MM
    highest = config.MAX_HEIGHT_MM
    return [
        f"Height must be {lowest} to {highest} mm, not {action.height_mm}"
        for action in redraws(plan)
        if action.height_mm is not None and not lowest <= action.height_mm <= highest
    ]


def redraws(plan: RecoveryPlan) -> list[RecoveryAction]:
    """Find the actions that draw liquid again.

    Args:
        plan: The plan to search.

    Returns:
        The reaspirate actions.
    """
    return [action for action in plan.actions if action.name == REASPIRATE]

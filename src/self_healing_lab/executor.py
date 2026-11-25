"""Carries out an approved recovery plan by sending steps back to the simulator."""

from dataclasses import replace

from self_healing_lab.faults import FaultySimulator
from self_healing_lab.models import (
    ActionName,
    Fault,
    PlanOutcome,
    PlanResult,
    RecoveryAction,
    RecoveryPlan,
    Step,
    StepType,
)


def execute_plan(plan: RecoveryPlan, step: Step, simulator: FaultySimulator) -> PlanResult:
    """Carry out a plan's actions in order, stopping if one fails.

    Args:
        plan: A plan the safety checker allowed.
        step: The step that failed.
        simulator: Carries out the steps.

    Returns:
        How the plan ended.
    """
    for action in plan.actions:
        if action.name == ActionName.PAUSE_AND_ALERT.value:
            return PlanResult(PlanOutcome.PAUSED)
        fault = run_steps(steps_for_action(action, step, simulator), simulator)
        if fault is not None:
            return PlanResult(PlanOutcome.FAILED, fault)
    return PlanResult(PlanOutcome.RECOVERED)


def run_steps(steps: list[Step], simulator: FaultySimulator) -> Fault | None:
    """Run steps in order, stopping at the first failure.

    Args:
        steps: The steps to run.
        simulator: Carries out the steps.

    Returns:
        The Fault that occurred, or None if every step worked.
    """
    for step in steps:
        fault = simulator.execute_step(step)
        if fault is not None:
            return fault
    return None


def steps_for_action(
    action: RecoveryAction, step: Step, simulator: FaultySimulator
) -> list[Step]:
    """Turn a recovery action into steps the simulator understands.

    Args:
        action: The action to turn into steps.
        step: The step that failed.
        simulator: Says whether a tip is attached.

    Returns:
        The steps, in order.
    """
    name = ActionName(action.name)
    if name == ActionName.RETRY_STEP:
        return [step]
    if name == ActionName.REASPIRATE:
        return [redraw_step(action, step)]
    if name == ActionName.GET_NEW_TIP:
        return new_tip_steps(simulator.get_state().has_tip)
    raise ValueError(f"{name.value} has no steps")


def redraw_step(action: RecoveryAction, step: Step) -> Step:
    """Build the step that draws liquid again.

    Args:
        action: The action, which may change the volume or height.
        step: The step that failed.

    Returns:
        The new step.
    """
    volume_ul = step.volume_ul if action.volume_ul is None else action.volume_ul
    height_mm = step.height_mm if action.height_mm is None else action.height_mm
    return replace(step, volume_ul=volume_ul, height_mm=height_mm)


def new_tip_steps(has_tip: bool) -> list[Step]:
    """Build the steps that get a new tip.

    Args:
        has_tip: Whether an old tip must be dropped first.

    Returns:
        The steps, in order.
    """
    pick_up = Step(StepType.PICK_UP_TIP)
    if has_tip:
        return [Step(StepType.DROP_TIP), pick_up]
    return [pick_up]

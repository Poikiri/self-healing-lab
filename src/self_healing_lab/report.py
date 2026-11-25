"""Writes the failure report that the AI reads."""

from self_healing_lab import config
from self_healing_lab.models import DeckState, Fault, FaultType, Step, StepType

FAULT_TEXT: dict[FaultType, str] = {
    FaultType.TIP_PICKUP_FAILED: "the tip didn't attach",
    FaultType.ASPIRATION_FAILED: "not enough liquid was drawn",
    FaultType.PLATE_MISSING: "the plate isn't on the deck",
}

ACTIONS_TEXT = f"""Choose 1 to {config.MAX_PLAN_LENGTH} of these actions:
- retry_step: run the failed step again
- get_new_tip: drop the tip, if any, and pick up a new one
- reaspirate: draw again, with an optional volume_ul and height_mm
- pause_and_alert: stop and ask a human

Rules:
- End by redoing the failed step once, or with pause_and_alert.
- After a failed tip pickup, get_new_tip counts as redoing the step.
- Get a new tip before drawing again only if the draw failed.
- If the plate is missing, the only choice is pause_and_alert.
- volume_ul can't be less than the step's volume, more than the well holds, or more than {config.TIP_CAPACITY_UL:g}.
- height_mm must be {config.MIN_HEIGHT_MM:g} to {config.MAX_HEIGHT_MM:g}."""


def build_report(fault: Fault, deck: DeckState) -> str:
    """Write the full report for a failure.

    Args:
        fault: What went wrong.
        deck: The deck right now.

    Returns:
        The report, ready to send to the AI.
    """
    lines = [
        f"Failed step: {describe_step(fault.step)}",
        f"What went wrong: {FAULT_TEXT[fault.type]}",
        f"Plates on deck: {', '.join(deck.plates) or 'none'}",
        f"Tip attached: {describe_tip(deck)}",
    ]
    if fault.step.plate in deck.plates:
        volume = deck.volume_for(fault.step)
        lines.append(f"Liquid in {fault.step.plate} {fault.step.well}: {volume:g} µL")
    return "\n".join(lines) + "\n\n" + ACTIONS_TEXT


def describe_step(step: Step) -> str:
    """Describe a step in plain words.

    Args:
        step: The step to describe.

    Returns:
        The description, such as "draw 100 µL from source A1".
    """
    if step.type == StepType.PICK_UP_TIP:
        return "pick up a tip"
    if step.type == StepType.DROP_TIP:
        return "drop the tip"
    place = f"{step.plate} {step.well}"
    if step.type == StepType.ASPIRATE:
        return f"draw {step.volume_ul:g} µL from {place}"
    return f"release {step.volume_ul:g} µL into {place}"


def describe_tip(deck: DeckState) -> str:
    """Describe the tip in plain words.

    Args:
        deck: The deck right now.

    Returns:
        The description, such as "yes, holding 0 µL".
    """
    if not deck.has_tip:
        return "no"
    return f"yes, holding {deck.tip_volume_ul:g} µL"

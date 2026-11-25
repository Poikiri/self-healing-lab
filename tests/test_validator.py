import math

import pytest

from self_healing_lab.models import (
    DeckState,
    Fault,
    FaultType,
    RecoveryAction,
    RecoveryPlan,
)
from self_healing_lab.protocol import build_protocol
from self_healing_lab.validator import validate_plan

PICK_UP, ASPIRATE, DISPENSE, _ = build_protocol(["A1"], 100.0)
TIP_FAULT = Fault(FaultType.TIP_PICKUP_FAILED, PICK_UP)
DRAW_FAULT = Fault(FaultType.ASPIRATION_FAILED, ASPIRATE)
PLATE_FAULT = Fault(FaultType.PLATE_MISSING, DISPENSE)
DECK = DeckState(["source", "destination"], True, 0.0, {"source A1": 200.0})


# Build a plan from action names and return the problems found.
def check(fault: Fault, names: list[str], retries_used: int = 0) -> list[str]:
    plan = RecoveryPlan(actions=[RecoveryAction(name=name) for name in names])
    return validate_plan(plan, fault, DECK, retries_used)


# Build a one-action redraw plan and return the problems found.
def check_redraw(
    volume_ul: float | None = None, height_mm: float | None = None, deck: DeckState = DECK
) -> list[str]:
    action = RecoveryAction(name="reaspirate", volume_ul=volume_ul, height_mm=height_mm)
    return validate_plan(RecoveryPlan(actions=[action]), DRAW_FAULT, deck, 0)


# Sensible plans are allowed.
@pytest.mark.parametrize(
    "fault, names",
    [
        (TIP_FAULT, ["retry_step"]),
        (TIP_FAULT, ["get_new_tip"]),
        (DRAW_FAULT, ["retry_step"]),
        (DRAW_FAULT, ["reaspirate"]),
        (DRAW_FAULT, ["get_new_tip", "reaspirate"]),
        (TIP_FAULT, ["pause_and_alert"]),
        (DRAW_FAULT, ["pause_and_alert"]),
        (PLATE_FAULT, ["pause_and_alert"]),
    ],
)
def test_good_plans(fault: Fault, names: list[str]) -> None:
    assert check(fault, names) == []


# Made-up actions are rejected.
def test_unknown_action() -> None:
    assert "Unknown action: call_a_friend" in check(DRAW_FAULT, ["call_a_friend"])


# Empty plans are rejected.
def test_empty_plan() -> None:
    assert check(DRAW_FAULT, []) == ["A plan needs 1 to 3 actions, not 0"]


# A plan of 3 actions is fine, but 4 is too many.
def test_too_many_actions() -> None:
    assert check(DRAW_FAULT, ["get_new_tip"] * 2 + ["retry_step"]) == []
    assert check(DRAW_FAULT, ["get_new_tip"] * 3 + ["retry_step"]) == [
        "A plan needs 1 to 3 actions, not 4"
    ]


# A missing plate can only lead to a pause.
@pytest.mark.parametrize(
    "names",
    [["retry_step"], ["reaspirate"], ["get_new_tip"], ["retry_step", "pause_and_alert"]],
)
def test_missing_plate_must_pause(names: list[str]) -> None:
    assert check(PLATE_FAULT, names) != []


# Nothing may follow an action that redoes the step, or a pause.
@pytest.mark.parametrize(
    "names",
    [["retry_step", "retry_step"], ["reaspirate", "retry_step"], ["pause_and_alert", "retry_step"]],
)
def test_must_stop_after_redo(names: list[str]) -> None:
    assert any("before the last action" in problem for problem in check(DRAW_FAULT, names))


# A plan must not end without redoing the step or pausing.
def test_must_redo_or_pause() -> None:
    assert check(DRAW_FAULT, ["get_new_tip"]) != []


# Drawing liquid can't fix a failed tip pickup.
def test_redraw_does_not_fix_tip() -> None:
    assert check(TIP_FAULT, ["reaspirate"]) != []


# A step already retried the maximum number of times can't be retried again.
@pytest.mark.parametrize(
    "fault, name",
    [
        (DRAW_FAULT, "retry_step"),
        (DRAW_FAULT, "reaspirate"),
        (TIP_FAULT, "get_new_tip"),
    ],
)
def test_too_many_retries(fault: Fault, name: str) -> None:
    assert check(fault, [name], retries_used=1) == ["The step can be retried at most 1 time(s)"]


# Pausing is still allowed after the retries run out.
def test_can_pause_after_retries() -> None:
    assert check(DRAW_FAULT, ["pause_and_alert"], retries_used=1) == []


# A redraw must take at least the step's volume and no more than the well holds.
@pytest.mark.parametrize(
    "volume_ul, allowed",
    [
        (100.0, True),
        (200.0, True),
        (99.0, False),
        (201.0, False),
        (-1.0, False),
        (math.nan, False),
        (math.inf, False),
    ],
)
def test_redraw_volume(volume_ul: float, allowed: bool) -> None:
    assert (check_redraw(volume_ul=volume_ul) == []) == allowed


# A redraw can't exceed the tip's capacity, even if the well holds more.
def test_tip_capacity() -> None:
    deck = DeckState(["source"], True, 0.0, {"source A1": 5000.0})
    assert check_redraw(volume_ul=1000.0, deck=deck) == []
    assert check_redraw(volume_ul=1001.0, deck=deck) != []


# A redraw height must be in range.
@pytest.mark.parametrize(
    "height_mm, allowed",
    [(0.0, True), (10.0, True), (-0.1, False), (10.1, False), (math.nan, False)],
)
def test_redraw_height(height_mm: float, allowed: bool) -> None:
    assert (check_redraw(height_mm=height_mm) == []) == allowed

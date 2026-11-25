import pytest

from self_healing_lab.executor import execute_plan, new_tip_steps, redraw_step
from self_healing_lab.faults import FaultySimulator
from self_healing_lab.models import (
    FaultType,
    PlanOutcome,
    PlanResult,
    RecoveryAction,
    RecoveryPlan,
    StepType,
)
from self_healing_lab.protocol import build_protocol
from self_healing_lab.simulator import Simulator

PICK_UP, ASPIRATE, DISPENSE, DROP = build_protocol(["A1"], 100.0)


# Build a plan from action names.
def make_plan(*names: str) -> RecoveryPlan:
    return RecoveryPlan(actions=[RecoveryAction(name=name) for name in names])


# Build a simulator that never fails on purpose, holding a tip if asked.
def make_simulator(with_tip: bool = False) -> FaultySimulator:
    simulator = FaultySimulator(Simulator(), 0.0, 1)
    if with_tip:
        simulator.execute_step(PICK_UP)
    return simulator


# Each way to fix a failed pickup ends with a tip attached.
@pytest.mark.parametrize("name", ["retry_step", "get_new_tip"])
def test_fix_pickup(name: str) -> None:
    simulator = make_simulator()
    result = execute_plan(make_plan(name), PICK_UP, simulator)
    assert result == PlanResult(PlanOutcome.RECOVERED)
    assert simulator.get_state().has_tip


# Each way to fix a failed draw ends with the right amount in the tip.
@pytest.mark.parametrize(
    "names", [["retry_step"], ["reaspirate"], ["get_new_tip", "reaspirate"]]
)
def test_fix_draw(names: list[str]) -> None:
    simulator = make_simulator(with_tip=True)
    result = execute_plan(make_plan(*names), ASPIRATE, simulator)
    assert result == PlanResult(PlanOutcome.RECOVERED)
    assert simulator.get_state().tip_volume_ul == 100.0


# After a fix, the rest of the protocol still works.
def test_protocol_continues_after_fix() -> None:
    simulator = make_simulator(with_tip=True)
    execute_plan(make_plan("get_new_tip", "reaspirate"), ASPIRATE, simulator)
    assert simulator.execute_step(DISPENSE) is None
    assert simulator.execute_step(DROP) is None
    assert simulator.get_state().well_volumes_ul["destination A1"] == 100.0


# Drawing extra works, and the leftover leaves with the tip.
def test_redraw_with_extra_volume() -> None:
    simulator = make_simulator(with_tip=True)
    plan = RecoveryPlan(
        actions=[RecoveryAction(name="reaspirate", volume_ul=150.0, height_mm=2.0)]
    )
    assert execute_plan(plan, ASPIRATE, simulator).outcome == PlanOutcome.RECOVERED
    assert simulator.get_state().tip_volume_ul == 150.0
    simulator.execute_step(DISPENSE)
    assert simulator.execute_step(DROP) is None
    assert simulator.get_state().well_volumes_ul["destination A1"] == 100.0


# A redraw keeps the original volume and height unless the plan changes them.
def test_redraw_step() -> None:
    assert redraw_step(RecoveryAction(name="reaspirate"), ASPIRATE) == ASPIRATE
    changed = redraw_step(
        RecoveryAction(name="reaspirate", volume_ul=120.0, height_mm=0.0), ASPIRATE
    )
    assert (changed.volume_ul, changed.height_mm) == (120.0, 0.0)


# An old tip is dropped first, but only if there is one.
def test_new_tip_steps() -> None:
    assert [s.type for s in new_tip_steps(True)] == [StepType.DROP_TIP, StepType.PICK_UP_TIP]
    assert [s.type for s in new_tip_steps(False)] == [StepType.PICK_UP_TIP]


# A pause runs nothing.
def test_pause() -> None:
    simulator = make_simulator()
    result = execute_plan(make_plan("pause_and_alert"), PICK_UP, simulator)
    assert result == PlanResult(PlanOutcome.PAUSED)
    assert not simulator.get_state().has_tip


# A fix can fail, and the actions after it don't run.
def test_failed_fix_stops() -> None:
    plain = Simulator()
    plain.execute_step(PICK_UP)
    simulator = FaultySimulator(plain, 1.0, 1)
    result = execute_plan(make_plan("get_new_tip", "reaspirate"), ASPIRATE, simulator)
    assert result.outcome == PlanOutcome.FAILED
    assert result.fault is not None
    assert result.fault.type == FaultType.TIP_PICKUP_FAILED
    assert simulator.get_state().well_volumes_ul["source A1"] == 200.0

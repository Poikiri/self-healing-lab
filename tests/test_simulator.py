import pytest
from pylabrobot.resources.errors import NoTipError

from self_healing_lab.models import FaultType, Step, StepType
from self_healing_lab.protocol import build_protocol
from self_healing_lab.simulator import Simulator


# A fresh deck has both plates, no tip, and a full source plate.
def test_starting_deck() -> None:
    state = Simulator().get_state()
    assert state.plates == ["source", "destination"]
    assert not state.has_tip
    assert state.well_volumes_ul["source A1"] == 200.0
    assert "destination A1" not in state.well_volumes_ul


# Running the four steps moves the liquid and drops the tip.
def test_protocol_moves_liquid() -> None:
    simulator = Simulator()
    for step in build_protocol(["A1"], 100.0):
        assert simulator.execute_step(step) is None
    state = simulator.get_state()
    assert state.well_volumes_ul["source A1"] == 100.0
    assert state.well_volumes_ul["destination A1"] == 100.0
    assert not state.has_tip


# After drawing liquid, the tip holds it.
def test_tip_holds_liquid_after_aspirate() -> None:
    simulator = Simulator()
    for step in build_protocol(["A1"], 100.0)[:2]:
        simulator.execute_step(step)
    state = simulator.get_state()
    assert state.has_tip
    assert state.tip_volume_ul == 100.0


# A whole 96-well plate works, using a fresh tip each time.
def test_full_plate() -> None:
    wells = [f"{row}{column}" for column in range(1, 13) for row in "ABCDEFGH"]
    simulator = Simulator()
    for step in build_protocol(wells, 100.0):
        assert simulator.execute_step(step) is None
    assert simulator.get_state().well_volumes_ul["destination H12"] == 100.0


# Using a plate that was removed reports a missing plate.
@pytest.mark.parametrize(
    "step_type, plate",
    [(StepType.ASPIRATE, "source"), (StepType.DISPENSE, "destination")],
)
def test_missing_plate(step_type: StepType, plate: str) -> None:
    simulator = Simulator()
    simulator.remove_plate(plate)
    fault = simulator.execute_step(Step(step_type, plate, "A1", 100.0))
    assert fault is not None
    assert fault.type == FaultType.PLATE_MISSING
    assert plate not in simulator.get_state().plates


# A mistake in our own code, like drawing with no tip, stops loudly.
def test_aspirate_without_tip_is_an_error() -> None:
    with pytest.raises(NoTipError):
        Simulator().execute_step(Step(StepType.ASPIRATE, "source", "A1", 100.0))

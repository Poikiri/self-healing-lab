import random

import pytest

from self_healing_lab.faults import FaultySimulator, choose_fault
from self_healing_lab.models import Fault, FaultType, Step, StepType
from self_healing_lab.protocol import build_protocol
from self_healing_lab.simulator import Simulator

PICK_UP, ASPIRATE, DISPENSE, DROP = build_protocol(["A1"], 100.0)


# At 100%, each kind of step fails only in the ways it can.
@pytest.mark.parametrize(
    "step, expected",
    [
        (PICK_UP, {FaultType.TIP_PICKUP_FAILED}),
        (ASPIRATE, {FaultType.ASPIRATION_FAILED, FaultType.PLATE_MISSING}),
        (DISPENSE, {FaultType.PLATE_MISSING}),
        (DROP, {None}),
    ],
)
def test_possible_faults(step: Step, expected: set[FaultType | None]) -> None:
    rng = random.Random(1)
    assert {choose_fault(step, 1.0, rng) for _ in range(50)} == expected


# The failure rate setting really controls how often steps fail.
@pytest.mark.parametrize("probability", [0.0, 0.2, 0.7, 1.0])
def test_failure_rate(probability: float) -> None:
    rng = random.Random(1)
    rolls = [choose_fault(PICK_UP, probability, rng) for _ in range(5000)]
    failures = sum(roll is not None for roll in rolls)
    assert failures / 5000 == pytest.approx(probability, abs=0.03)


# The same seed gives the same die rolls, and a different seed does not.
def test_seed_repeats_failures() -> None:
    def roll(seed: int) -> list[FaultType | None]:
        rng = random.Random(seed)
        return [choose_fault(ASPIRATE, 0.5, rng) for _ in range(50)]

    assert roll(7) == roll(7)
    assert roll(7) != roll(8)


# At 0%, the whole protocol works.
def test_no_failures_at_zero() -> None:
    simulator = FaultySimulator(Simulator(), 0.0, 1)
    assert [simulator.execute_step(s) for s in (PICK_UP, ASPIRATE, DISPENSE, DROP)] == [None] * 4
    assert simulator.get_state().well_volumes_ul["destination A1"] == 100.0


# A failed tip pickup leaves the robot with no tip.
def test_failed_pickup_leaves_no_tip() -> None:
    simulator = FaultySimulator(Simulator(), 1.0, 1)
    assert simulator.execute_step(PICK_UP) == Fault(FaultType.TIP_PICKUP_FAILED, PICK_UP)
    assert not simulator.get_state().has_tip


# A failed draw moves no liquid.
def test_failed_aspiration_moves_no_liquid(monkeypatch: pytest.MonkeyPatch) -> None:
    plain = Simulator()
    plain.execute_step(PICK_UP)
    simulator = FaultySimulator(plain, 1.0, 1)
    monkeypatch.setattr(
        "self_healing_lab.faults.choose_fault", lambda *args: FaultType.ASPIRATION_FAILED
    )
    assert simulator.execute_step(ASPIRATE) == Fault(FaultType.ASPIRATION_FAILED, ASPIRATE)
    state = simulator.get_state()
    assert state.tip_volume_ul == 0.0
    assert state.well_volumes_ul["source A1"] == 200.0


# A missing plate is really gone, and failing again is safe.
def test_missing_plate_stays_gone() -> None:
    simulator = FaultySimulator(Simulator(), 1.0, 1)
    for _ in range(2):
        assert simulator.execute_step(DISPENSE) == Fault(FaultType.PLATE_MISSING, DISPENSE)
    assert simulator.get_state().plates == ["source"]

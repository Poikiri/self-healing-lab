import pytest

from self_healing_lab.agent import AgentError, FakeAgent
from self_healing_lab.faults import FaultySimulator
from self_healing_lab.models import (
    DeckState,
    Fault,
    FaultType,
    PlanOutcome,
    RecoveryAction,
    RecoveryPlan,
)
from self_healing_lab.protocol import build_protocol
from self_healing_lab.runner import run_protocol
from self_healing_lab.simulator import Simulator

STEPS = build_protocol(["A1"], 100.0)


# A pretend AI that always suggests an action that isn't allowed.
class BadAgent:
    def propose_plan(self, fault: Fault, deck: DeckState) -> RecoveryPlan:
        return RecoveryPlan(actions=[RecoveryAction(name="call_a_friend")])


# A pretend AI that can't be reached.
class BrokenAgent:
    def propose_plan(self, fault: Fault, deck: DeckState) -> RecoveryPlan:
        raise AgentError("no internet")


# Choose exactly which die rolls fail, in order. Later rolls don't fail.
def set_rolls(monkeypatch: pytest.MonkeyPatch, rolls: list[FaultType | None]) -> None:
    remaining = list(rolls)

    def roll(*args: object) -> FaultType | None:
        return remaining.pop(0) if remaining else None

    monkeypatch.setattr("self_healing_lab.faults.choose_fault", roll)


# Build a simulator whose die rolls are set by the test.
def make_simulator() -> FaultySimulator:
    return FaultySimulator(Simulator(), 0.0, 1)


# With no failures, every step runs.
def test_no_failures() -> None:
    result = run_protocol(STEPS, make_simulator(), FakeAgent())
    assert result.completed
    assert result.steps_run == STEPS
    assert result.recoveries == []


# A failed pickup or draw is fixed, and the protocol finishes correctly.
@pytest.mark.parametrize(
    "rolls",
    [[FaultType.TIP_PICKUP_FAILED], [None, FaultType.ASPIRATION_FAILED]],
)
def test_fixed_failure(
    monkeypatch: pytest.MonkeyPatch, rolls: list[FaultType | None]
) -> None:
    set_rolls(monkeypatch, rolls)
    simulator = make_simulator()
    result = run_protocol(STEPS, simulator, FakeAgent())
    assert result.completed
    assert result.steps_run == STEPS
    assert [record.is_fixed() for record in result.recoveries] == [True]
    assert simulator.get_state().well_volumes_ul["destination A1"] == 100.0


# A missing plate pauses the run.
def test_missing_plate_pauses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    set_rolls(monkeypatch, [None, FaultType.PLATE_MISSING])
    result = run_protocol(STEPS, make_simulator(), FakeAgent())
    assert not result.completed
    assert result.steps_run == STEPS[:2]
    assert result.recoveries[0].result.outcome == PlanOutcome.PAUSED
    assert "PAUSED" in capsys.readouterr().out


# A fix that fails pauses the run.
def test_failed_fix_pauses(monkeypatch: pytest.MonkeyPatch) -> None:
    set_rolls(monkeypatch, [FaultType.TIP_PICKUP_FAILED] * 2)
    result = run_protocol(STEPS, make_simulator(), FakeAgent())
    assert not result.completed
    assert result.recoveries[0].result.outcome == PlanOutcome.FAILED


# A rejected plan never runs, and pauses the run.
def test_rejected_plan_pauses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    set_rolls(monkeypatch, [FaultType.TIP_PICKUP_FAILED])
    simulator = make_simulator()
    result = run_protocol(STEPS, simulator, BadAgent())
    assert not result.completed
    assert result.recoveries[0].problems != []
    assert result.recoveries[0].result is None
    assert not simulator.get_state().has_tip
    assert "REJECTED" in capsys.readouterr().out


# Two different failures in one run can both be fixed.
def test_two_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    set_rolls(
        monkeypatch, [FaultType.TIP_PICKUP_FAILED, None, FaultType.ASPIRATION_FAILED]
    )
    result = run_protocol(STEPS, make_simulator(), FakeAgent())
    assert result.completed
    assert len(result.recoveries) == 2


# If the AI can't be reached, the run pauses instead of crashing.
def test_agent_error_pauses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    set_rolls(monkeypatch, [FaultType.TIP_PICKUP_FAILED])
    result = run_protocol(STEPS, make_simulator(), BrokenAgent())
    assert not result.completed
    assert result.recoveries[0].plan is None
    assert result.recoveries[0].problems == ["no internet"]
    output = capsys.readouterr().out
    assert "AI ERROR: no internet" in output
    assert "PAUSED" in output

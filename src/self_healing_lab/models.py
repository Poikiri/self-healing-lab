"""Simple typed objects shared by the project."""

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel


class StepType(Enum):
    """The kinds of steps the robot can do."""

    PICK_UP_TIP = "pick_up_tip"
    ASPIRATE = "aspirate"
    DISPENSE = "dispense"
    DROP_TIP = "drop_tip"


@dataclass(frozen=True)
class Step:
    """One instruction for the robot. Tip steps use only the type."""

    type: StepType
    plate: str | None = None
    well: str | None = None
    volume_ul: float | None = None
    height_mm: float | None = None


class FaultType(Enum):
    """The ways a step can fail."""

    TIP_PICKUP_FAILED = "tip_pickup_failed"
    ASPIRATION_FAILED = "aspiration_failed"
    PLATE_MISSING = "plate_missing"


@dataclass(frozen=True)
class Fault:
    """What went wrong, and on which step."""

    type: FaultType
    step: Step


@dataclass(frozen=True)
class DeckState:
    """What is on the deck and in the tip. Wells are named like "source A1"."""

    plates: list[str]
    has_tip: bool
    tip_volume_ul: float
    well_volumes_ul: dict[str, float]

    def volume_for(self, step: Step) -> float:
        """Find how much liquid is in a step's well.

        Args:
            step: A step that uses a well.

        Returns:
            The volume in microliters, or 0 if the well is empty or gone.
        """
        return self.well_volumes_ul.get(f"{step.plate} {step.well}", 0.0)


class ActionName(Enum):
    """The fixes the AI may choose from."""

    RETRY_STEP = "retry_step"
    GET_NEW_TIP = "get_new_tip"
    REASPIRATE = "reaspirate"
    PAUSE_AND_ALERT = "pause_and_alert"


class RecoveryAction(BaseModel):
    """One action the AI suggests. The name is plain text until it is checked."""

    name: str
    volume_ul: float | None = None
    height_mm: float | None = None


class RecoveryPlan(BaseModel):
    """The actions the AI suggests, in order."""

    actions: list[RecoveryAction]


class PlanOutcome(Enum):
    """How carrying out a plan ended."""

    RECOVERED = "recovered"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass(frozen=True)
class PlanResult:
    """How carrying out a plan ended, and the new failure if there was one."""

    outcome: PlanOutcome
    fault: Fault | None = None


@dataclass(frozen=True)
class RecoveryRecord:
    """One failure and what was done about it.

    The plan is None if the AI gave none. The result is None if no plan ran.
    """

    fault: Fault
    plan: RecoveryPlan | None
    problems: list[str]
    result: PlanResult | None

    def is_fixed(self) -> bool:
        """Check whether the failure was fixed.

        Args:
            None.

        Returns:
            True if the fix worked.
        """
        return self.result is not None and self.result.outcome == PlanOutcome.RECOVERED


@dataclass(frozen=True)
class RunResult:
    """What happened during a whole run."""

    steps_run: list[Step]
    recoveries: list[RecoveryRecord]
    completed: bool

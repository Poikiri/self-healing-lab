"""Makes steps fail on purpose."""

import random

from self_healing_lab.models import DeckState, Fault, FaultType, Step, StepType
from self_healing_lab.simulator import Simulator

POSSIBLE_FAULTS: dict[StepType, list[FaultType]] = {
    StepType.PICK_UP_TIP: [FaultType.TIP_PICKUP_FAILED],
    StepType.ASPIRATE: [FaultType.ASPIRATION_FAILED, FaultType.PLATE_MISSING],
    StepType.DISPENSE: [FaultType.PLATE_MISSING],
    StepType.DROP_TIP: [],
}


def choose_fault(step: Step, probability: float, rng: random.Random) -> FaultType | None:
    """Roll the die to see whether a step fails, and how.

    Args:
        step: The step about to run.
        probability: The chance of failure, from 0 to 1.
        rng: The source of random numbers.

    Returns:
        The kind of failure, or None if the step should run normally.
    """
    faults = POSSIBLE_FAULTS[step.type]
    if not faults or rng.random() >= probability:
        return None
    return rng.choice(faults)


class FaultySimulator:
    """A simulator whose steps sometimes fail."""

    def __init__(self, simulator: Simulator, probability: float, seed: int) -> None:
        """Wrap a simulator.

        Args:
            simulator: The simulator that carries out steps.
            probability: The chance that a step fails, from 0 to 1.
            seed: Repeats the same die rolls when reused.

        Returns:
            None.
        """
        self._simulator = simulator
        self._probability = probability
        self._rng = random.Random(seed)

    def execute_step(self, step: Step) -> Fault | None:
        """Carry out one step, which may fail on purpose.

        Args:
            step: The step to carry out.

        Returns:
            The Fault that occurred, or None if the step worked.
        """
        fault_type = choose_fault(step, self._probability, self._rng)
        if fault_type is None:
            return self._simulator.execute_step(step)
        if fault_type == FaultType.PLATE_MISSING:
            self._simulator.remove_plate(step.plate)
        return Fault(fault_type, step)

    def get_state(self) -> DeckState:
        """Describe the deck right now.

        Args:
            None.

        Returns:
            The plates, tip, and liquid.
        """
        return self._simulator.get_state()

"""Builds the list of steps the robot follows."""

from self_healing_lab import config
from self_healing_lab.models import Step, StepType


def build_transfer(well: str, volume_ul: float) -> list[Step]:
    """Build the four steps that move liquid for one well.

    Args:
        well: The well to use on both plates, such as "A1".
        volume_ul: How much liquid to move, in microliters.

    Returns:
        The four steps, in order.
    """
    return [
        Step(StepType.PICK_UP_TIP),
        Step(StepType.ASPIRATE, config.SOURCE_PLATE, well, volume_ul),
        Step(StepType.DISPENSE, config.DESTINATION_PLATE, well, volume_ul),
        Step(StepType.DROP_TIP),
    ]


def build_protocol(wells: list[str], volume_ul: float) -> list[Step]:
    """Build the steps for every well.

    Args:
        wells: The wells to transfer, in order.
        volume_ul: How much liquid to move per well, in microliters.

    Returns:
        All the steps, in order.
    """
    steps: list[Step] = []
    for well in wells:
        steps.extend(build_transfer(well, volume_ul))
    return steps

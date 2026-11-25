from self_healing_lab import config
from self_healing_lab.models import Step, StepType
from self_healing_lab.protocol import build_protocol, build_transfer


# One transfer is the four steps, in the right order.
def test_transfer_has_the_four_steps_in_order() -> None:
    assert build_transfer("A1", 100.0) == [
        Step(StepType.PICK_UP_TIP),
        Step(StepType.ASPIRATE, "source", "A1", 100.0),
        Step(StepType.DISPENSE, "destination", "A1", 100.0),
        Step(StepType.DROP_TIP),
    ]


# The default settings make one transfer.
def test_default_protocol_has_four_steps() -> None:
    steps = build_protocol(config.TRANSFER_WELLS, config.TRANSFER_VOLUME_UL)
    assert len(steps) == 4


# More wells means more transfers, in the same order as the wells.
def test_protocol_repeats_for_each_well() -> None:
    steps = build_protocol(["A1", "B1"], 50.0)
    assert steps == build_transfer("A1", 50.0) + build_transfer("B1", 50.0)

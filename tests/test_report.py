from self_healing_lab.models import DeckState, Fault, FaultType
from self_healing_lab.protocol import build_protocol
from self_healing_lab.report import ACTIONS_TEXT, build_report, describe_step

PICK_UP, ASPIRATE, DISPENSE, DROP = build_protocol(["A1"], 100.0)
DECK = DeckState(
    ["source", "destination"], True, 0.0, {"source A1": 200.0, "source B1": 200.0}
)


# A failed draw gives the whole report, with only the failed step's well.
def test_failed_draw_report() -> None:
    report = build_report(Fault(FaultType.ASPIRATION_FAILED, ASPIRATE), DECK)
    assert report == (
        "Failed step: draw 100 µL from source A1\n"
        "What went wrong: not enough liquid was drawn\n"
        "Plates on deck: source, destination\n"
        "Tip attached: yes, holding 0 µL\n"
        "Liquid in source A1: 200 µL\n\n" + ACTIONS_TEXT
    )


# A failed tip pickup has no well to report.
def test_failed_tip_report() -> None:
    deck = DeckState(["source", "destination"], False, 0.0, {"source A1": 200.0})
    report = build_report(Fault(FaultType.TIP_PICKUP_FAILED, PICK_UP), deck)
    assert "Tip attached: no" in report
    assert "Liquid in" not in report


# A missing plate has no well to report.
def test_missing_plate_report() -> None:
    deck = DeckState(["source"], True, 100.0, {"source A1": 100.0})
    report = build_report(Fault(FaultType.PLATE_MISSING, DISPENSE), deck)
    assert "Plates on deck: source\n" in report
    assert "Tip attached: yes, holding 100 µL" in report
    assert "Liquid in" not in report


# Every kind of step has a plain description.
def test_step_descriptions() -> None:
    assert [describe_step(step) for step in (PICK_UP, ASPIRATE, DISPENSE, DROP)] == [
        "pick up a tip",
        "draw 100 µL from source A1",
        "release 100 µL into destination A1",
        "drop the tip",
    ]

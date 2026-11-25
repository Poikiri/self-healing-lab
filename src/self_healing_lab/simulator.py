"""A pretend liquid handler. This is the only file that uses PyLabRobot."""

import asyncio
import io
from collections.abc import Coroutine
from contextlib import redirect_stdout

from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.liquid_handling.backends import LiquidHandlerChatterboxBackend
from pylabrobot.resources import (
    PLT_CAR_L5AC_A00,
    TIP_CAR_480_A00,
    Plate,
    TipSpot,
    cor_96_wellplate_360uL_Fb,
    hamilton_96_tiprack_1000uL_filter,
    set_tip_tracking,
    set_volume_tracking,
)
from pylabrobot.resources.hamilton import STARLetDeck

from self_healing_lab import config
from self_healing_lab.models import DeckState, Fault, FaultType, Step, StepType


def run_quietly(action: Coroutine) -> None:
    """Run one PyLabRobot action and hide what it prints.

    Args:
        action: The PyLabRobot action to run.

    Returns:
        None.
    """
    with redirect_stdout(io.StringIO()):
        asyncio.run(action)


class Simulator:
    """Carries out protocol steps on a simulated deck."""

    def __init__(self) -> None:
        """Set up a fresh robot and deck.

        Args:
            None.

        Returns:
            None.
        """
        set_tip_tracking(True)
        set_volume_tracking(True)
        self._robot = LiquidHandler(
            backend=LiquidHandlerChatterboxBackend(num_channels=1),
            deck=STARLetDeck(),
        )
        run_quietly(self._robot.setup())
        self._add_tips()
        self._add_plates()
        self._fill_source_plate()

    def execute_step(self, step: Step) -> Fault | None:
        """Carry out one step.

        Args:
            step: The step to carry out.

        Returns:
            The Fault that occurred, or None if the step worked.
        """
        if step.plate is not None and not self._robot.deck.has_resource(step.plate):
            return Fault(FaultType.PLATE_MISSING, step)
        run_quietly(self._build_action(step))
        return None

    def remove_plate(self, name: str) -> None:
        """Take a plate off the deck, if it is there.

        Args:
            name: The plate to remove.

        Returns:
            None.
        """
        if self._robot.deck.has_resource(name):
            self._robot.deck.get_resource(name).unassign()

    def get_state(self) -> DeckState:
        """Describe the deck right now.

        Args:
            None.

        Returns:
            The plates, tip, and liquid. Empty wells are left out.
        """
        tip = self._robot.head[0]
        plates = self._plates_on_deck()
        return DeckState(
            plates=[plate.name for plate in plates],
            has_tip=tip.has_tip,
            tip_volume_ul=tip.get_tip().tracker.get_used_volume() if tip.has_tip else 0.0,
            well_volumes_ul=self._well_volumes(plates),
        )

    def _add_tips(self) -> None:
        """Put a full tip rack on the deck.

        Args:
            None.

        Returns:
            None.
        """
        carrier = TIP_CAR_480_A00(name="tip_carrier")
        self._tip_rack = hamilton_96_tiprack_1000uL_filter(name="tips")
        carrier[0] = self._tip_rack
        self._robot.deck.assign_child_resource(carrier, rails=config.TIP_RACK_RAIL)

    def _add_plates(self) -> None:
        """Put the source and destination plates on the deck.

        Args:
            None.

        Returns:
            None.
        """
        carrier = PLT_CAR_L5AC_A00(name="plate_carrier")
        self._plates = [
            cor_96_wellplate_360uL_Fb(name=config.SOURCE_PLATE),
            cor_96_wellplate_360uL_Fb(name=config.DESTINATION_PLATE),
        ]
        for position, plate in enumerate(self._plates):
            carrier[position] = plate
        self._robot.deck.assign_child_resource(carrier, rails=config.PLATE_RAIL)

    def _fill_source_plate(self) -> None:
        """Put the starting liquid in every source well.

        Args:
            None.

        Returns:
            None.
        """
        for well in self._robot.deck.get_resource(config.SOURCE_PLATE).get_all_items():
            well.tracker.set_volume(config.SOURCE_WELL_VOLUME_UL)

    def _build_action(self, step: Step) -> Coroutine:
        """Turn a step into a PyLabRobot action.

        Args:
            step: The step to turn into an action.

        Returns:
            The action, ready to run.
        """
        if step.type == StepType.PICK_UP_TIP:
            return self._robot.pick_up_tips([self._next_tip()])
        if step.type == StepType.DROP_TIP:
            return self._robot.discard_tips()
        well = self._robot.deck.get_resource(step.plate)[step.well]
        if step.type == StepType.ASPIRATE:
            return self._robot.aspirate(
                well, vols=[step.volume_ul], liquid_height=[step.height_mm]
            )
        return self._robot.dispense(well, vols=[step.volume_ul])

    def _next_tip(self) -> TipSpot:
        """Find the next unused tip in the rack.

        Args:
            None.

        Returns:
            The position of the tip.
        """
        for spot in self._tip_rack.get_all_items():
            if spot.tracker.has_tip:
                return spot
        raise RuntimeError("The tip rack is empty.")

    def _plates_on_deck(self) -> list[Plate]:
        """Find the plates that are still on the deck.

        Args:
            None.

        Returns:
            The plates on the deck.
        """
        return [plate for plate in self._plates if self._robot.deck.has_resource(plate.name)]

    def _well_volumes(self, plates: list[Plate]) -> dict[str, float]:
        """Read how much liquid is in each well.

        Args:
            plates: The plates to read.

        Returns:
            The volume of each well that has liquid, such as {"source A1": 200.0}.
        """
        volumes: dict[str, float] = {}
        for plate in plates:
            for well in plate.get_all_items():
                volume = well.tracker.get_used_volume()
                if volume > 0:
                    volumes[f"{plate.name} {well.get_identifier()}"] = volume
        return volumes

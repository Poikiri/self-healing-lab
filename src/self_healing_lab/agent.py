"""The AI that suggests recovery plans."""

from typing import Protocol

from anthropic import Anthropic, AnthropicError
from pydantic import ValidationError

from self_healing_lab import config
from self_healing_lab.models import (
    ActionName,
    DeckState,
    Fault,
    FaultType,
    RecoveryAction,
    RecoveryPlan,
)
from self_healing_lab.report import build_report

CANNED_ACTIONS: dict[FaultType, list[ActionName]] = {
    FaultType.TIP_PICKUP_FAILED: [ActionName.GET_NEW_TIP],
    FaultType.ASPIRATION_FAILED: [ActionName.GET_NEW_TIP, ActionName.REASPIRATE],
    FaultType.PLATE_MISSING: [ActionName.PAUSE_AND_ALERT],
}

INSTRUCTIONS = "You help a lab robot recover from failures. Reply with a recovery plan."


class AgentError(Exception):
    """The AI could not be reached or gave no usable plan."""


class Agent(Protocol):
    """Anything that can suggest a recovery plan."""

    def propose_plan(self, fault: Fault, deck: DeckState) -> RecoveryPlan:
        """Suggest a plan for a failure.

        Args:
            fault: What went wrong.
            deck: The deck right now.

        Returns:
            The suggested plan.
        """
        ...


class FakeAgent:
    """A pretend AI that always gives the same plan for the same failure."""

    def propose_plan(self, fault: Fault, deck: DeckState) -> RecoveryPlan:
        """Look up the canned plan for a failure.

        Args:
            fault: What went wrong.
            deck: The deck right now, which the pretend AI ignores.

        Returns:
            The canned plan.
        """
        actions = [RecoveryAction(name=name.value) for name in CANNED_ACTIONS[fault.type]]
        return RecoveryPlan(actions=actions)


class ClaudeAgent:
    """Asks Claude for a plan."""

    def __init__(self, client: Anthropic) -> None:
        """Set up the agent.

        Args:
            client: The connection to Claude.

        Returns:
            None.
        """
        self._client = client

    def propose_plan(self, fault: Fault, deck: DeckState) -> RecoveryPlan:
        """Ask Claude for a plan.

        Args:
            fault: What went wrong.
            deck: The deck right now.

        Returns:
            The suggested plan.
        """
        try:
            response = self._client.messages.parse(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                system=INSTRUCTIONS,
                messages=[{"role": "user", "content": build_report(fault, deck)}],
                output_format=RecoveryPlan,
            )
        except AnthropicError as error:
            raise AgentError(f"Claude could not be reached: {error}") from error
        except ValidationError as error:
            raise AgentError("Claude's reply was not a plan") from error
        if response.stop_reason != "end_turn" or response.parsed_output is None:
            raise AgentError(f"Claude gave no plan ({response.stop_reason})")
        return response.parsed_output

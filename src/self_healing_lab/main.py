"""The command that runs the project."""

import argparse
import os

from anthropic import Anthropic

from self_healing_lab import config
from self_healing_lab.agent import Agent, ClaudeAgent, FakeAgent
from self_healing_lab.faults import FaultySimulator
from self_healing_lab.printer import print_summary
from self_healing_lab.protocol import build_protocol
from self_healing_lab.runner import run_protocol
from self_healing_lab.simulator import Simulator


def probability(text: str) -> float:
    """Read a probability typed by the user.

    Args:
        text: What the user typed.

    Returns:
        The probability, from 0 to 1.
    """
    value = float(text)
    if not 0 <= value <= 1:
        raise argparse.ArgumentTypeError("must be from 0 to 1")
    return value


def parse_options(words: list[str] | None = None) -> argparse.Namespace:
    """Read the command's options.

    Args:
        words: The options to read, or None to use what the user typed.

    Returns:
        The options.
    """
    parser = argparse.ArgumentParser(description="Run the self-healing lab cell.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument(
        "--fault-probability", type=probability, default=config.FAULT_PROBABILITY
    )
    parser.add_argument("--fake-llm", action="store_true", help="use the pretend AI")
    options = parser.parse_args(words)
    if not options.fake_llm and not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("set ANTHROPIC_API_KEY to use Claude, or add --fake-llm")
    return options


def build_agent(fake_llm: bool) -> Agent:
    """Choose the AI and say which one is in use.

    Args:
        fake_llm: Whether to use the pretend AI.

    Returns:
        The AI.
    """
    if fake_llm:
        print("Using the pretend AI")
        return FakeAgent()
    print(f"Using {config.CLAUDE_MODEL}")
    return ClaudeAgent(Anthropic(timeout=config.CLAUDE_TIMEOUT_SECONDS))


def main(words: list[str] | None = None) -> None:
    """Run the protocol once.

    Args:
        words: The options to use, or None to use what the user typed.

    Returns:
        None.
    """
    options = parse_options(words)
    steps = build_protocol(config.TRANSFER_WELLS, config.TRANSFER_VOLUME_UL)
    simulator = FaultySimulator(Simulator(), options.fault_probability, options.seed)
    agent = build_agent(options.fake_llm)
    print(f"Seed: {options.seed}, failure rate: {options.fault_probability:.0%}\n")
    result = run_protocol(steps, simulator, agent)
    print_summary(result, len(steps))


if __name__ == "__main__":
    main()

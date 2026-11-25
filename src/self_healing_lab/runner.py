"""Runs a whole protocol and recovers from failures."""

from self_healing_lab import printer
from self_healing_lab.agent import Agent, AgentError
from self_healing_lab.executor import execute_plan
from self_healing_lab.faults import FaultySimulator
from self_healing_lab.models import Fault, RecoveryRecord, RunResult, Step
from self_healing_lab.validator import validate_plan


def run_protocol(steps: list[Step], simulator: FaultySimulator, agent: Agent) -> RunResult:
    """Run every step, stopping if a failure can't be fixed.

    Args:
        steps: The steps to run, in order.
        simulator: Carries out the steps.
        agent: Suggests plans for failures.

    Returns:
        What happened.
    """
    steps_run: list[Step] = []
    recoveries: list[RecoveryRecord] = []
    for number, step in enumerate(steps, start=1):
        printer.print_step(number, step)
        steps_run.append(step)
        fault = simulator.execute_step(step)
        if fault is None:
            continue
        record = recover(fault, simulator, agent)
        recoveries.append(record)
        if not record.is_fixed():
            printer.print_alert()
            return RunResult(steps_run, recoveries, completed=False)
    return RunResult(steps_run, recoveries, completed=True)


def recover(fault: Fault, simulator: FaultySimulator, agent: Agent) -> RecoveryRecord:
    """Try to fix one failure.

    Args:
        fault: What went wrong.
        simulator: Carries out the plan.
        agent: Suggests the plan.

    Returns:
        What was done about the failure.
    """
    printer.print_fault(fault)
    deck = simulator.get_state()
    try:
        plan = agent.propose_plan(fault, deck)
    except AgentError as error:
        printer.print_agent_error(str(error))
        return RecoveryRecord(fault, plan=None, problems=[str(error)], result=None)
    printer.print_plan(plan)
    # Each failed step gets only one plan, so it was never retried before.
    problems = validate_plan(plan, fault, deck, retries_used=0)
    printer.print_check(problems)
    if problems:
        return RecoveryRecord(fault, plan, problems, result=None)
    result = execute_plan(plan, fault.step, simulator)
    printer.print_plan_result(result)
    return RecoveryRecord(fault, plan, problems, result)

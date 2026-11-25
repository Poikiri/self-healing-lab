import json

import httpx2
import pytest
from anthropic import Anthropic

from self_healing_lab import config
from self_healing_lab.agent import AgentError, ClaudeAgent, FakeAgent
from self_healing_lab.models import DeckState, Fault, FaultType
from self_healing_lab.protocol import build_protocol
from self_healing_lab.report import build_report
from self_healing_lab.validator import validate_plan

PICK_UP, ASPIRATE, DISPENSE, _ = build_protocol(["A1"], 100.0)
DECK = DeckState(["source", "destination"], True, 0.0, {"source A1": 200.0})


# The pretend AI gives the expected plan, and the safety checker allows it.
@pytest.mark.parametrize(
    "fault, names",
    [
        (Fault(FaultType.TIP_PICKUP_FAILED, PICK_UP), ["get_new_tip"]),
        (Fault(FaultType.ASPIRATION_FAILED, ASPIRATE), ["get_new_tip", "reaspirate"]),
        (Fault(FaultType.PLATE_MISSING, DISPENSE), ["pause_and_alert"]),
    ],
)
def test_canned_plans_are_allowed(fault: Fault, names: list[str]) -> None:
    plan = FakeAgent().propose_plan(fault, DECK)
    assert [action.name for action in plan.actions] == names
    assert validate_plan(plan, fault, DECK, retries_used=0) == []


DRAW_FAULT = Fault(FaultType.ASPIRATION_FAILED, ASPIRATE)


# Build a Claude agent whose internet is fake: it gets this reply and saves what it sends.
def make_claude(reply: httpx2.Response, sent: list[dict]) -> ClaudeAgent:
    def answer(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return reply

    http_client = httpx2.Client(transport=httpx2.MockTransport(answer))
    return ClaudeAgent(Anthropic(api_key="test", http_client=http_client, max_retries=0))


# Build a reply from Claude containing this text.
def claude_reply(text: str, stop_reason: str = "end_turn") -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": config.CLAUDE_MODEL,
            "content": [{"type": "text", "text": text}] if text else [],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )


# Claude gets the failure report and the plan's shape, and its reply becomes a plan.
def test_claude_plan() -> None:
    sent: list[dict] = []
    reply = claude_reply('{"actions": [{"name": "reaspirate", "volume_ul": 120}]}')
    plan = make_claude(reply, sent).propose_plan(DRAW_FAULT, DECK)
    assert plan.actions[0].name == "reaspirate"
    assert plan.actions[0].volume_ul == 120.0
    assert sent[0]["model"] == config.CLAUDE_MODEL
    assert sent[0]["messages"][0]["content"] == build_report(DRAW_FAULT, DECK)
    assert sent[0]["output_config"]["format"]["type"] == "json_schema"


# Anything other than a finished plan is an error.
@pytest.mark.parametrize(
    "reply",
    [
        claude_reply("sorry, no idea"),
        claude_reply('{"actions": ['),
        claude_reply("", stop_reason="refusal"),
        claude_reply('{"actions": []}', stop_reason="max_tokens"),
        httpx2.Response(401, json={"error": {"type": "authentication_error"}}),
        httpx2.Response(529, json={"error": {"type": "overloaded_error"}}),
    ],
)
def test_claude_errors(reply: httpx2.Response) -> None:
    with pytest.raises(AgentError):
        make_claude(reply, []).propose_plan(DRAW_FAULT, DECK)


# Having no internet is an error too.
def test_claude_no_internet() -> None:
    def fail(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no internet")

    http_client = httpx2.Client(transport=httpx2.MockTransport(fail))
    client = Anthropic(api_key="test", http_client=http_client, max_retries=0)
    with pytest.raises(AgentError):
        ClaudeAgent(client).propose_plan(DRAW_FAULT, DECK)

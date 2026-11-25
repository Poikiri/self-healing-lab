import pytest

from self_healing_lab.main import main


# The same options print exactly the same log.
def test_same_seed_same_log(capsys: pytest.CaptureFixture) -> None:
    options = ["--fake-llm", "--seed", "3", "--fault-probability", "0.5"]
    main(options)
    first = capsys.readouterr().out
    main(options)
    assert capsys.readouterr().out == first
    assert "Using the pretend AI" in first


# With no failures, the summary says the run completed.
def test_summary(capsys: pytest.CaptureFixture) -> None:
    main(["--fake-llm", "--fault-probability", "0"])
    output = capsys.readouterr().out
    assert "Result: completed\nSteps run: 4 of 4\nFailures: 0, fixed: 0" in output


# Bad options, or no key for Claude, stop the command.
@pytest.mark.parametrize(
    "options", [[], ["--fake-llm", "--fault-probability", "2"]]
)
def test_bad_options(monkeypatch: pytest.MonkeyPatch, options: list[str]) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        main(options)

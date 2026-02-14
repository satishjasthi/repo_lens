from __future__ import annotations

import pytest

from repo_lens.command_agent import (
    AgentRunResult,
    CommandExecution,
    PlannedCommand,
    run_command_agent,
)
from repo_lens.config import Settings


class _StaticResponseClient:
    def __init__(self, response: str):
        self.response = response
        self.messages: list[list[dict[str, str]]] = []

    def chat_messages(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
        self.messages.append(messages)
        return self.response


class _SequencedClient:
    def __init__(self, responses: list[str]):
        self._responses = responses
        self._index = 0
        self.messages: list[list[dict[str, str]]] = []

    def chat_messages(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
        self.messages.append(messages)
        response = self._responses[self._index]
        self._index += 1
        return response


def test_plan_git_commands_parses_valid_plan() -> None:
    client = _StaticResponseClient(
        '{"commands": [{"command": "git rev-list --max-parents=0 HEAD", "reason": "Find root"}]}'
    )
    plan = plan_git_commands(client, context="Repo", question="Who created the repo?")
    assert len(plan) == 1
    assert plan[0].command.startswith("git rev-list")
    assert "Question" in client.messages[0][1]["content"]


def test_plan_git_commands_rejects_forbidden_subcommand() -> None:
    client = _StaticResponseClient(
        '{"commands": [{"command": "git reset --hard HEAD", "reason": "Bad"}]}'
    )
    with pytest.raises(CommandPlanError):
        plan_git_commands(client, context="Repo", question="Danger")


def test_execute_git_plan_runs_commands(tiny_repo) -> None:
    plan = [PlannedCommand(command="git rev-parse HEAD", reason="Current head")]
    results = execute_git_plan(plan, repo_path=tiny_repo.worktree)
    assert len(results) == 1
    assert results[0].success is True
    assert len(results[0].output.strip()) == 40


def test_execute_git_plan_captures_failures(tiny_repo) -> None:
    plan = [PlannedCommand(command="git show not-a-real-sha", reason="Expect failure")]
    results = execute_git_plan(plan, repo_path=tiny_repo.worktree)
    assert len(results) == 1
    assert results[0].success is False
    assert "fatal" in results[0].output.lower()


def test_generate_final_answer_receives_command_outputs() -> None:
    execs = [
        CommandExecution(
            command="git rev-parse HEAD",
            reason="Need SHA",
            output="abcdef",
            success=True,
        )
    ]
    client = _StaticResponseClient("Final answer")
    answer = generate_final_answer(
        client,
        context="Repo",
        question="What is HEAD?",
        executions=execs,
    )
    assert answer == "Final answer"
    assert "git rev-parse HEAD" in client.messages[0][1]["content"]


def test_run_command_agent_executes_plan(tiny_repo) -> None:
    responses = [
        '{"commands": [{"command": "git rev-parse HEAD", "reason": "Need SHA"}]}',
        "HEAD is 123",
    ]
    client = _SequencedClient(responses)
    settings = Settings(repo_path=tiny_repo.worktree)
    result = run_command_agent(settings=settings, client=client, question="What is HEAD?")
    assert isinstance(result, AgentRunResult)
    assert result.plan[0].command == "git rev-parse HEAD"
    assert result.executions[0].success is True
    assert result.answer == "HEAD is 123"
    assert len(client.messages) == 2

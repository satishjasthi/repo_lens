from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from repo_lens.cli import app
from repo_lens.command_agent import AgentRunResult, CommandExecution, PlannedCommand

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from .conftest import RepoUnderTest

runner = CliRunner()


def _git(args: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _configure_identity(repo_path: Path) -> None:
    _git(["config", "user.name", "Repo Lens Peer"], cwd=repo_path)
    _git(["config", "user.email", "repo-lens-peer@example.com"], cwd=repo_path)


def test_git_status_command(tiny_repo: "RepoUnderTest") -> None:
    result = runner.invoke(app, ["git", "status", "--repo", str(tiny_repo.worktree)])
    assert result.exit_code == 0
    assert "## " in result.stdout


def test_git_log_command(tiny_repo: "RepoUnderTest") -> None:
    result = runner.invoke(
        app,
        ["git", "log", "--limit", "3", "--repo", str(tiny_repo.worktree)],
    )
    assert result.exit_code == 0
    lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    commit_lines = [line for line in lines if re.match(r"^[0-9a-f]{7}", line)]
    assert commit_lines
    assert len(commit_lines) <= 3
    assert all("|" in line for line in commit_lines)


def test_git_run_command(tiny_repo: "RepoUnderTest") -> None:
    expected = _git(["rev-parse", "HEAD"], cwd=tiny_repo.worktree)
    result = runner.invoke(
        app,
        ["git", "run", "--repo", str(tiny_repo.worktree), "rev-parse", "HEAD"],
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == expected


def test_git_create_branch_command(tiny_repo: "RepoUnderTest") -> None:
    branch_name = "feature/repo-lens-tests"
    result = runner.invoke(
        app, ["git", "create-branch", branch_name, "--repo", str(tiny_repo.worktree)]
    )
    assert result.exit_code == 0
    current_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=tiny_repo.worktree)
    assert current_branch == branch_name


def test_git_pull_and_push_roundtrip(tmp_path: Path, tiny_repo: "RepoUnderTest") -> None:
    repo_path = tiny_repo.worktree
    remote_path = tiny_repo.remote
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)

    peer_path = tmp_path / "peer"
    _git(["clone", str(remote_path), str(peer_path)], cwd=tmp_path)
    _configure_identity(peer_path)

    remote_file = peer_path / "REMOTE_CHANGE.md"
    remote_file.write_text("remote change", encoding="utf-8")
    _git(["add", remote_file.name], cwd=peer_path)
    _git(["commit", "-m", "Add remote change"], cwd=peer_path)
    _git(["push", "origin", branch], cwd=peer_path)

    pull_result = runner.invoke(
        app, ["git", "pull", "origin", branch, "--repo", str(repo_path)]
    )
    assert pull_result.exit_code == 0
    assert (repo_path / remote_file.name).exists()

    local_file = repo_path / "LOCAL_CHANGE.md"
    local_file.write_text("local change", encoding="utf-8")
    _git(["add", local_file.name], cwd=repo_path)
    _git(["commit", "-m", "Add local change"], cwd=repo_path)

    push_result = runner.invoke(
        app, ["git", "push", "origin", branch, "--repo", str(repo_path)]
    )
    assert push_result.exit_code == 0


def test_shell_command_executes_inside_repo(tmp_path: Path, tiny_repo: "RepoUnderTest") -> None:
    marker = tiny_repo.worktree / "shell-proof.txt"
    if marker.exists():
        marker.unlink()

    result = runner.invoke(
        app, ["shell", "pwd > shell-proof.txt", "--repo", str(tiny_repo.worktree)]
    )
    assert result.exit_code == 0
    assert marker.exists()


def test_ask_command_uses_repo_context(monkeypatch: pytest.MonkeyPatch, tiny_repo: "RepoUnderTest") -> None:
    captured: dict[str, str] = {}

    class DummyClient:
        def __enter__(self):  # pragma: no cover - simple context management
            return self

        def __exit__(self, *_exc_info):  # pragma: no cover - simple context management
            return False

        def chat(self, *, context: str, question: str) -> str:
            captured["context"] = context
            captured["question"] = question
            return "Stubbed answer"

    monkeypatch.setattr("repo_lens.cli.create_llm_client", lambda _settings: DummyClient())

    result = runner.invoke(
        app,
        [
            "ask",
            "Summarize the README",
            "--repo",
            str(tiny_repo.worktree),
            "--grep",
            "README",
        ],
    )

    assert result.exit_code == 0
    assert "Stubbed answer" in result.stdout
    assert "Summarize the README" == captured["question"]
    assert str(tiny_repo.worktree) in captured["context"]


def test_agent_command_invokes_command_agent(monkeypatch: pytest.MonkeyPatch, tiny_repo: "RepoUnderTest") -> None:
    fake_result = AgentRunResult(
        plan=[PlannedCommand(command="git rev-parse HEAD", reason="Need SHA")],
        executions=[
            CommandExecution(
                command="git rev-parse HEAD",
                reason="Need SHA",
                output="123",
                success=True,
            )
        ],
        answer="Planned answer",
    )

    captured: dict[str, str] = {}

    def _fake_run(*, settings, client, question):
        captured["question"] = question
        return fake_result

    monkeypatch.setattr("repo_lens.cli.run_command_agent", _fake_run)

    result = runner.invoke(
        app,
        [
            "agent",
            "Who created the repo?",
            "--repo",
            str(tiny_repo.worktree),
        ],
    )

    assert result.exit_code == 0
    assert "Planned answer" in result.stdout
    assert "git rev-parse HEAD" in result.stdout
    assert captured["question"] == "Who created the repo?"


def test_git_checkout_command_switches_branches(tiny_repo: "RepoUnderTest") -> None:
    repo_path = tiny_repo.worktree
    starting_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    feature_branch = "feature/repo-lens-tests"

    create_result = runner.invoke(
        app,
        ["git", "create-branch", feature_branch, "--repo", str(repo_path)],
    )
    assert create_result.exit_code == 0

    checkout_result = runner.invoke(
        app,
        ["git", "checkout", starting_branch, "--repo", str(repo_path)],
    )
    assert checkout_result.exit_code == 0
    current_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    assert current_branch == starting_branch


def test_top_level_repo_option_applies_to_git_commands(tiny_repo: "RepoUnderTest") -> None:
    result = runner.invoke(
        app, ["--repo", str(tiny_repo.worktree), "git", "status"], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert "## " in result.stdout


def test_repo_env_var_used_when_flag_missing(tiny_repo: "RepoUnderTest") -> None:
    env = {**os.environ, "REPO_LENS_REPO": str(tiny_repo.worktree)}
    result = runner.invoke(app, ["git", "status"], env=env, catch_exceptions=False)
    assert result.exit_code == 0
    assert "## " in result.stdout

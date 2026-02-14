from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from repo_lens.command_agent import (
    AgentRunResult,
    CommandExecution,
    GitTool,
    run_command_agent,
)
from repo_lens.config import Settings


def test_git_tool_executes_valid_command(tiny_repo) -> None:
    settings = Settings(repo_path=tiny_repo.worktree)
    executions = []
    tool = GitTool(settings, executions)
    
    output = tool.forward("git rev-parse HEAD")
    
    assert len(output.strip()) == 40
    assert len(executions) == 1
    assert executions[0].command == "git rev-parse HEAD"
    assert executions[0].success is True


def test_git_tool_rejects_forbidden_subcommand(tiny_repo) -> None:
    settings = Settings(repo_path=tiny_repo.worktree)
    executions = []
    tool = GitTool(settings, executions)
    
    output = tool.forward("git reset --hard HEAD")
    
    assert "not allowed" in output
    assert len(executions) == 0  # Should not even record forbidden ones as git executions? 
    # Actually current implementation checks BEFORE run_git, and doesn't record to executions list if it returns early with error string.
    # Let's verify that behavior in the code.


def test_git_tool_captures_failures(tiny_repo) -> None:
    settings = Settings(repo_path=tiny_repo.worktree)
    executions = []
    tool = GitTool(settings, executions)
    
    output = tool.forward("git show not-a-real-sha")
    
    assert "Git error" in output
    assert len(executions) == 1
    assert executions[0].success is False


@patch("repo_lens.command_agent.CodeAgent")
@patch("repo_lens.command_agent.LiteLLMModel")
def test_run_command_agent_wraps_result(mock_model, mock_agent_class, tiny_repo) -> None:
    mock_agent = mock_agent_class.return_value
    mock_agent.run.return_value = "Final Answer"
    
    settings = Settings(repo_path=tiny_repo.worktree)
    
    # We need to simulate some executions happening during agent run
    # Since executions is a list passed to GitTool, we can't easily inject it unless we mock more.
    # But we can just check if result.answer is set correctly.
    
    result = run_command_agent(settings=settings, question="What is HEAD?")
    
    assert isinstance(result, AgentRunResult)
    assert result.answer == "Final Answer"
    mock_agent.run.assert_called_once()

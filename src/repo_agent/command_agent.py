from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smolagents import CodeAgent, LiteLLMModel, Tool

from .config import (
    ALLOWED_SUBCOMMANDS,
    MAX_OUTPUT_CHARS,
    Settings,
)
from .context_builder import gather_repo_context
from .git_utils import GitError, run_git


class AgentError(RuntimeError):
    """Base error for command agent failures."""


@dataclass(slots=True)
class PlannedCommand:
    command: str
    reason: str


@dataclass(slots=True)
class CommandExecution:
    command: str
    reason: str
    output: str
    success: bool


@dataclass(slots=True)
class AgentRunResult:
    plan: list[PlannedCommand]
    executions: list[CommandExecution]
    answer: str


class GitTool(Tool):
    name = "git"
    description = (
        "Run read-only Git commands to inspect the repository history and state. "
        f"Allowed subcommands: {', '.join(sorted(ALLOWED_SUBCOMMANDS))}. "
        "Commands must start with 'git'."
    )
    inputs = {
        "command": {
            "type": "string",
            "description": "The git command to execute, e.g., 'git log -n 5'.",
        }
    }
    output_type = "string"

    def __init__(self, settings: Settings, executions: list[CommandExecution]):
        super().__init__()
        self.settings = settings
        self.executions = executions

    def forward(self, command: str) -> str:
        try:
            # 1. Basic validation
            parts = shlex.split(command)
            if not parts or parts[0] != "git":
                return "Error: Command must start with 'git'."
            if len(parts) == 1:
                return "Error: Command must include a subcommand, e.g., 'git log'."
            
            subcommand = parts[1]
            if subcommand not in ALLOWED_SUBCOMMANDS:
                return (
                    f"Error: Subcommand '{subcommand}' is not allowed. "
                    f"Allowed: {', '.join(sorted(ALLOWED_SUBCOMMANDS))}."
                )

            # 2. Execution
            git_args = parts[1:]
            output = run_git(git_args, self.settings.repo_path)
            success = True
            
            # 3. Truncate for the model
            display_output = _truncate_output(output)
            
            # 4. Record for CLI display
            # Note: Smolagents handles its own 'reasoning', but we record the execution
            self.executions.append(
                CommandExecution(
                    command=command,
                    reason="Step in agent reasoning loop",
                    output=display_output,
                    success=success,
                )
            )
            return output
        except GitError as exc:
            err_msg = str(exc)
            self.executions.append(
                CommandExecution(
                    command=command,
                    reason="Step in agent reasoning loop",
                    output=err_msg,
                    success=False,
                )
            )
            return f"Git error: {err_msg}"
        except Exception as exc:
            return f"Unexpected error: {exc}"


def _truncate_output(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "<no output>"
    if len(stripped) <= MAX_OUTPUT_CHARS:
        return stripped
    return stripped[: MAX_OUTPUT_CHARS - 20].rstrip() + "\n...[truncated]"


def run_command_agent(
    *,
    settings: Settings,
    question: str,
) -> AgentRunResult:
    # 1. Prepare context for the initial prompt
    context = gather_repo_context(settings)
    
    # 2. Setup smolagents
    model = LiteLLMModel(
        model_id=settings.llm_model,
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key,
    )
    
    executions: list[CommandExecution] = []
    git_tool = GitTool(settings, executions)
    
    agent = CodeAgent(
        tools=[git_tool],
        model=model,
        add_base_tools=False,
        max_steps=6,
    )
    
    # 3. Execute
    full_prompt = (
        f"Repository context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Use the 'git' tool iteratively to find information if the context is insufficient. "
        "Provide a concise final answer."
    )
    
    try:
        final_answer = agent.run(full_prompt)
    except Exception as exc:
        raise AgentError(f"Agent execution failed: {exc}") from exc
    
    # 4. Wrap result
    # For now, we don't have a static 'plan' like the old version, 
    # so we populate it from executions or leave it empty.
    plan = [PlannedCommand(command=e.command, reason=e.reason) for e in executions]
    
    return AgentRunResult(
        plan=plan,
        executions=executions,
        answer=str(final_answer),
    )

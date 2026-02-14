from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .config import (
    ALLOWED_SUBCOMMANDS,
    MAX_COMMANDS,
    MAX_OUTPUT_CHARS,
    Settings,
)
from .context_builder import gather_repo_context
from .git_utils import GitError, run_git
from .llm_client import LiteLLMClient


class AgentError(RuntimeError):
    """Base error for command agent failures."""


class CommandPlanError(AgentError):
    """Raised when the LLM returns an invalid command plan."""


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


def _strip_code_fence(text: str) -> str:
    trimmed = text.strip()
    if trimmed.startswith("```") and trimmed.endswith("```"):
        inner = trimmed.split("\n", 1)[-1]
        inner = inner.rsplit("```", 1)[0]
        return inner.strip()
    return trimmed


def _load_plan_json(raw: str) -> dict:
    candidate = _strip_code_fence(raw)
    # Strip thinking tags that some models (like Nemotron) include
    # Remove everything before </think> if present
    if "</think>" in candidate:
        candidate = candidate.split("</think>", 1)[-1].strip()
    # Also try to remove <think>...</think> blocks using regex
    candidate = re.sub(r'<think>.*?</think>', '', candidate, flags=re.DOTALL).strip()
    
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise CommandPlanError(f"LLM returned invalid JSON: {candidate}") from exc


def plan_git_commands(
    client: LiteLLMClient,
    *,
    settings: Settings,
    context: str,
    question: str,
) -> list[PlannedCommand]:
    messages = [
        {"role": "system", "content": settings.plan_system_prompt},
        {
            "role": "user",
            "content": (
                "Repository context:\n"
                f"{context}\n\n"
                f"Question: {question}\n"
                f"Return at most {MAX_COMMANDS} commands."
            ),
        },
    ]
    raw_plan = client.chat_messages(messages)
    data = _load_plan_json(raw_plan)
    commands_field = data.get("commands", [])
    if not isinstance(commands_field, list):
        raise CommandPlanError("LLM response is missing a 'commands' list.")

    plan: list[PlannedCommand] = []
    for entry in commands_field[:MAX_COMMANDS]:
        command = entry.get("command")
        reason = entry.get("reason")
        if not isinstance(command, str) or not isinstance(reason, str):
            raise CommandPlanError("Each command must include 'command' and 'reason' strings.")
        _validate_command(command)
        plan.append(PlannedCommand(command=command.strip(), reason=reason.strip()))
    return plan


def _validate_command(command: str) -> None:
    parts = shlex.split(command)
    if not parts or parts[0] != "git":
        raise CommandPlanError("Commands must start with 'git'.")
    if len(parts) == 1:
        raise CommandPlanError("Commands must include a subcommand, e.g., 'git log'.")
    subcommand = parts[1]
    if subcommand not in ALLOWED_SUBCOMMANDS:
        raise CommandPlanError(
            f"Subcommand '{subcommand}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_SUBCOMMANDS))}."
        )


def execute_git_plan(
    plan: list[PlannedCommand],
    *,
    repo_path: Path,
) -> list[CommandExecution]:
    results: list[CommandExecution] = []
    for item in plan:
        parts = shlex.split(item.command)
        git_args = parts[1:]
        try:
            output = run_git(git_args, repo_path)
            success = True
        except GitError as exc:  # pragma: no cover - simple flow
            output = str(exc)
            success = False
        results.append(
            CommandExecution(
                command=item.command,
                reason=item.reason,
                output=_truncate_output(output),
                success=success,
            )
        )
    return results


def _truncate_output(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "<no output>"
    if len(stripped) <= MAX_OUTPUT_CHARS:
        return stripped
    return stripped[: MAX_OUTPUT_CHARS - 20].rstrip() + "\n...[truncated]"


def generate_final_answer(
    client: LiteLLMClient,
    *,
    settings: Settings,
    context: str,
    question: str,
    executions: list[CommandExecution],
) -> str:
    if executions:
        command_blocks = []
        for result in executions:
            block = (
                f"Command: {result.command}\n"
                f"Reason: {result.reason}\n"
                f"Success: {'yes' if result.success else 'no'}\n"
                f"Output:\n{result.output}"
            )
            command_blocks.append(block)
        commands_text = "\n\n".join(command_blocks)
    else:
        commands_text = "No commands were executed. Answer using the repository context only."

    messages = [
        {"role": "system", "content": settings.answer_system_prompt},
        {
            "role": "user",
            "content": (
                "Repository context:\n"
                f"{context}\n\n"
                f"Question: {question}\n\n"
                f"Executed command outputs:\n{commands_text}\n\n"
                "Provide a concise answer that cites commands or commit hashes when possible."
            ),
        },
    ]
    return client.chat_messages(messages)


def run_command_agent(
    *,
    settings: Settings,
    client: LiteLLMClient,
    question: str,
) -> AgentRunResult:
    context = gather_repo_context(settings)
    plan = plan_git_commands(client, settings=settings, context=context, question=question)
    executions = execute_git_plan(plan, repo_path=settings.repo_path)
    answer = generate_final_answer(
        client,
        settings=settings,
        context=context,
        question=question,
        executions=executions,
    )
    return AgentRunResult(plan=plan, executions=executions, answer=answer)

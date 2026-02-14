from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .command_agent import AgentError, run_command_agent
from .config import Settings
from .context_builder import gather_repo_context
from .git_utils import run_git
from .llm_client import create_llm_client

app = typer.Typer(help="Git-aware repository assistant powered by LiteLLM and smolagents")
git_app = typer.Typer(help="Thin wrappers around git CLI")
app.add_typer(git_app, name="git")
console = Console()


def _provider_label(settings: Settings) -> str:
    return f"{settings.llm_provider.title()} ({settings.llm_model})"


def _format_plan(plan: list) -> str:
    if not plan:
        return "No additional Git commands were required; using existing context."
    lines: list[str] = []
    for idx, item in enumerate(plan, start=1):
        lines.append(f"{idx}. {item.command}")
        lines.append(f"   Reason: {item.reason}")
    return "\n".join(lines)


def _print_command_outputs(executions: list) -> None:
    if not executions:
        return
    for result in executions:
        status = "success" if result.success else "failed"
        body = f"Reason: {result.reason}\n\n{result.output}"
        console.print(
            Panel(
                body,
                title=f"$ {result.command} ({status})",
                expand=False,
            )
        )


def _repo_option() -> Path | None:
    return typer.Option(
        None,
        "--repo",
        "-r",
        help=(
            "Path to the Git repository. Defaults to the current working directory "
            "or the value of $REPO_LENS_REPO."
        ),
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    )


def _effective_repo(ctx: typer.Context, explicit_repo: Optional[Path]) -> Optional[Path]:
    if explicit_repo:
        return explicit_repo
    if ctx.obj is None:
        return None
    return ctx.obj.get("repo")


def _settings(ctx: typer.Context, repo: Optional[Path]) -> Settings:
    settings = Settings()
    effective_repo = _effective_repo(ctx, repo)
    if effective_repo:
        settings.repo_path = effective_repo
    return settings


@app.callback()
def _app_callback(ctx: typer.Context, repo: Optional[Path] = _repo_option()) -> None:
    ctx.obj = ctx.obj or {}
    if repo:
        ctx.obj["repo"] = repo


@app.command()
def ask(
    ctx: typer.Context,
    question: str = typer.Argument(..., help="Your natural-language question"),
    repo: Optional[Path] = _repo_option(),
    grep: Optional[str] = typer.Option(None, help="Optional git --grep hint"),
) -> None:
    """Ask the configured LLM about the repository."""

    settings = _settings(ctx, repo)
    provider_label = _provider_label(settings)
    context = gather_repo_context(settings, grep=grep)
    console.print(
        Panel.fit(
            f"Context gathered. Querying {provider_label}...",
            title="repo-lens",
        )
    )

    with create_llm_client(settings) as client:
        answer = client.chat(context=context, question=question)

    console.print(Panel(answer, title=provider_label, expand=False))


@app.command()
def agent(
    ctx: typer.Context,
    question: str = typer.Argument(..., help="Question to answer using Git commands"),
    repo: Optional[Path] = _repo_option(),
) -> None:
    """Plan and execute Git commands to answer the question."""

    settings = _settings(ctx, repo)
    provider_label = _provider_label(settings)
    console.print(Panel.fit(f"Running smolagent with {provider_label}...", title="repo-lens"))

    try:
        result = run_command_agent(settings=settings, question=question)
    except AgentError as exc:
        console.print(Panel(str(exc), title="repo-lens", style="red"))
        raise typer.Exit(1) from exc

    if result.executions:
        console.print(
            Panel(
                _format_plan(result.plan),
                title="Executed Git commands",
                expand=False,
            )
        )
        _print_command_outputs(result.executions)
    
    console.print(Panel(result.answer, title=provider_label, expand=False))


@git_app.command("status")
def git_status(ctx: typer.Context, repo: Optional[Path] = _repo_option()) -> None:
    settings = _settings(ctx, repo)
    console.print(run_git(["status", "-sb"], settings.repo_path))


@git_app.command("pull")
def git_pull(
    ctx: typer.Context,
    remote: str = typer.Argument("origin"),
    branch: Optional[str] = typer.Argument(None),
    repo: Optional[Path] = _repo_option(),
) -> None:
    settings = _settings(ctx, repo)
    args = ["pull", remote]
    if branch:
        args.append(branch)
    console.print(run_git(args, settings.repo_path))


@git_app.command("push")
def git_push(
    ctx: typer.Context,
    remote: str = typer.Argument("origin"),
    branch: Optional[str] = typer.Argument(None),
    repo: Optional[Path] = _repo_option(),
) -> None:
    settings = _settings(ctx, repo)
    args = ["push", remote]
    if branch:
        args.append(branch)
    console.print(run_git(args, settings.repo_path))


@git_app.command("checkout")
def git_checkout(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="Branch, commit, or -b new-branch"),
    repo: Optional[Path] = _repo_option(),
) -> None:
    settings = _settings(ctx, repo)
    console.print(run_git(["checkout", *shlex.split(target)], settings.repo_path))


@git_app.command("create-branch")
def git_create_branch(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    base: str = typer.Option("HEAD", help="Base commit"),
    repo: Optional[Path] = _repo_option(),
) -> None:
    settings = _settings(ctx, repo)
    console.print(run_git(["checkout", "-b", name, base], settings.repo_path))


@git_app.command("log")
def git_log(
    ctx: typer.Context,
    limit: int = typer.Option(5, "--limit", "-n"),
    repo: Optional[Path] = _repo_option(),
) -> None:
    settings = _settings(ctx, repo)
    console.print(
        run_git(
            [
                "log",
                f"-n{limit}",
                "--date=short",
                "--pretty=format:%h | %an | %ad | %s",
            ],
            settings.repo_path,
        )
    )


@git_app.command("run")
def git_run(
    ctx: typer.Context,
    args: list[str] = typer.Argument(..., help="Exact git arguments"),
    repo: Optional[Path] = _repo_option(),
) -> None:
    settings = _settings(ctx, repo)
    console.print(run_git(args, settings.repo_path))


@app.command()
def shell(
    ctx: typer.Context,
    command: str = typer.Argument(..., help="Shell command to run inside repo"),
    repo: Optional[Path] = _repo_option(),
) -> None:
    """Execute an arbitrary command within the repo root."""

    settings = _settings(ctx, repo)
    try:
        subprocess.run(command, cwd=settings.repo_path, check=True, shell=True)
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode) from exc


if __name__ == "__main__":  # pragma: no cover
    app()

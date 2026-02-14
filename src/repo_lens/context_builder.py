from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .config import Settings
from .git_utils import try_git


def gather_repo_context(settings: Settings, *, grep: str | None = None) -> str:
    repo = settings.repo_path
    parts = [f"Repository: {repo}"]

    parts.append(f"Branch: {try_git(['rev-parse', '--abbrev-ref', 'HEAD'], repo)}")
    parts.append("Status:\n" + try_git(["status", "-sb"], repo))

    log_output = try_git(
        [
            "log",
            f"-n{settings.commit_history_limit}",
            "--date=short",
            "--pretty=format:%h | %an | %ad | %s",
        ],
        repo,
    )
    parts.append("Recent commits:\n" + log_output)

    if grep:
        parts.append(
            "Grep results:\n"
            + try_git(
                [
                    "log",
                    "--date=short",
                    "--pretty=format:%h | %an | %ad | %s",
                    f"--grep={grep}",
                ],
                repo,
            )
        )

    if settings.include_diff:
        parts.append("Staged diff:\n" + try_git(["diff", "--staged"], repo))
        parts.append("Working diff:\n" + try_git(["diff"], repo))

    return "\n\n".join(part for part in parts if part)

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable


class GitError(RuntimeError):
    pass


def run_git(args: Iterable[str], repo_path: Path) -> str:
    cmd = ["git", *args]
    try:
        completed = subprocess.run(
            cmd,
            cwd=repo_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - just bubble up message
        raise GitError(exc.stderr.strip() or exc.stdout.strip() or str(exc)) from exc
    return completed.stdout.strip()


def try_git(args: Iterable[str], repo_path: Path) -> str:
    try:
        return run_git(args, repo_path)
    except GitError as exc:
        return f"<git error: {exc}>"

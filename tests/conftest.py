from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_URL = "https://github.com/martinmimigames/tiny-music-player.git"


@dataclass(slots=True)
class RepoUnderTest:
    worktree: Path
    remote: Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _configure_identity(repo_path: Path) -> None:
    _run(["git", "config", "user.name", "Repo Lens Tests"], cwd=repo_path)
    _run(["git", "config", "user.email", "repo-lens@example.com"], cwd=repo_path)


@pytest.fixture(scope="session")
def upstream_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base_dir = tmp_path_factory.mktemp("tiny-music-player-upstream")
    target = base_dir / "source"
    _run(["git", "clone", REPO_URL, str(target)])
    return target


@pytest.fixture()
def tiny_repo(tmp_path: Path, upstream_repo: Path) -> RepoUnderTest:
    remote = tmp_path / "remote.git"
    worktree = tmp_path / "tiny-music-player"
    _run(["git", "clone", "--bare", str(upstream_repo), str(remote)])
    _run(["git", "clone", str(remote), str(worktree)])
    _configure_identity(worktree)
    return RepoUnderTest(worktree=worktree, remote=remote)

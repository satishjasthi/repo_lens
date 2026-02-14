from __future__ import annotations

from typing import TYPE_CHECKING

from repo_lens.config import Settings
from repo_lens.context_builder import gather_repo_context

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from .conftest import RepoUnderTest


def test_gather_repo_context_includes_recent_commits(tiny_repo: "RepoUnderTest") -> None:
    settings = Settings()
    settings.repo_path = tiny_repo.worktree
    settings.commit_history_limit = 3

    context = gather_repo_context(settings)

    assert str(tiny_repo.worktree) in context
    assert "Recent commits" in context
    assert "Branch:" in context

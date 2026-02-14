from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, cast

from dotenv import find_dotenv, load_dotenv

# Load .env from current working directory or parent directories
load_dotenv(find_dotenv(usecwd=True))

# Provider = Literal["nemotron", "openai"]  # Removed in favor of generic strings

# Constants moved from command_agent.py to avoid circular imports
ALLOWED_SUBCOMMANDS: Final[frozenset[str]] = frozenset(
    {
        "log",
        "show",
        "rev-list",
        "rev-parse",
        "describe",
        "status",
        "shortlog",
        "cat-file",
        "diff",
        "ls-tree",
        "grep",
        "blame",
    }
)
MAX_COMMANDS: Final[int] = 4
MAX_OUTPUT_CHARS: Final[int] = 4000

# Default prompts
DEFAULT_SYSTEM_PROMPT = (
    "You are a repository analyst. Use the provided Git context to answer questions. "
    "Always cite commit hashes and authors when relevant."
)

DEFAULT_PLAN_SYSTEM_PROMPT = (
    "You are a Git analyst. Decide which read-only Git commands to run to answer the user's "
    "question. Choose from the subcommands: "
    + ", ".join(sorted(ALLOWED_SUBCOMMANDS))
    + ". Return STRICT JSON: {\"commands\": [{\"command\": \"git ...\", \"reason\": \"...\"}]} with at most "
    f"{MAX_COMMANDS} entries. "
    "IMPORTANT: Commands are executed directly, NOT through a shell. "
    "NEVER use shell operators (|, >, <), command substitution ($( ), ` `), or variable expansion ($VAR)."
)

DEFAULT_ANSWER_SYSTEM_PROMPT = (
    "You are a repository analyst. Use ONLY the provided Git command outputs (and repository context) "
    "to answer the question. Cite commit hashes, authors, and dates when relevant. If the data is "
    "insufficient, say so explicitly."
)


def _resolve_repo_path() -> Path:
    repo_env = os.getenv("REPO_LENS_REPO")
    if repo_env:
        return Path(repo_env).expanduser()
    return Path.cwd()


@dataclass(slots=True)
class Settings:
    repo_path: Path = field(default_factory=_resolve_repo_path)
    
    # Generic LLM Configuration
    # provider can be "openai", "anthropic", "vertex_ai", "ollama", etc.
    # For local LLMs (LM Studio, etc.), usually use "openai" and set api_base.
    llm_provider: str = field(default_factory=lambda: os.getenv("REPO_LENS_PROVIDER", "openai"))
    llm_model: str = field(default_factory=lambda: os.getenv("REPO_LENS_MODEL", "gpt-4o-mini"))
    llm_api_base: str | None = field(default_factory=lambda: os.getenv("REPO_LENS_API_BASE"))
    llm_api_key: str | None = field(default_factory=lambda: os.getenv("REPO_LENS_API_KEY", os.getenv("OPENAI_API_KEY")))
    
    request_timeout: float = field(
        default_factory=lambda: float(os.getenv("REPO_LENS_TIMEOUT", "60"))
    )
    commit_history_limit: int = field(
        default_factory=lambda: int(os.getenv("REPO_LENS_COMMITS", "8"))
    )
    include_diff: bool = field(
        default_factory=lambda: os.getenv("REPO_LENS_INCLUDE_DIFF", "0") == "1"
    )
    
    # Prompts
    system_prompt: str = field(
        default_factory=lambda: os.getenv("REPO_LENS_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)
    )
    plan_system_prompt: str = field(
        default_factory=lambda: os.getenv("REPO_LENS_PLAN_PROMPT", DEFAULT_PLAN_SYSTEM_PROMPT)
    )
    answer_system_prompt: str = field(
        default_factory=lambda: os.getenv("REPO_LENS_ANSWER_PROMPT", DEFAULT_ANSWER_SYSTEM_PROMPT)
    )

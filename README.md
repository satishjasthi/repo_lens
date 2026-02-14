# repo-agent

A Python CLI that pairs Git insights with OpenAI or Nemotron responses. It can:

* Query your repository history using natural language (`repo-agent ask ...`).
* Surface structured Git data (status, commit history, grep results) before every LLM call.
* Run common Git actions (status, pull, push, new branch, custom commands) from the same interface.

## Installation

### Run inside this repo with `uv run`

1. Change into the project directory and install dependencies:
   ```bash
   cd tools/repo-agent
   uv sync
   ```
2. Execute the CLI directly via `uv run` (this reuses the `.venv` created during `uv sync`):
   ```bash
   uv run repo-agent --help
   uv run repo-agent git status
   ```

### Install the CLI globally

You can install the published CLI into your `~/.local/bin` (or the platform-specific scripts directory) and invoke it from any path:

```bash
cd tools/repo-agent
uv tool install --from . repo-agent  # use --force to update in-place later
repo-agent --repo /path/to/repo git status
repo-agent ask "Summarize README" --repo /path/to/repo
```

Because the command is now available on your `PATH`, you can run it from anywhere as long as you either execute it inside the target repository or supply `--repo /path/to/repo` at the beginning of the command. The `--repo` flag also works after each sub-command (`repo-agent git status --repo ...`).

## Pointing `repo-agent` at a repository

* **Current directory** – running the CLI from inside a Git checkout just works.
* **CLI flag** – `repo-agent --repo ~/code/tiny-music-player ask "What changed in v0.2?"`.
* **Environment variable** – set `REPO_AGENT_REPO=/absolute/path` once (add it to `.env` if you prefer).

All commands—`ask`, `git status`, `git pull`, `shell`, etc.—respect the global `--repo/-r` option as well as per-command overrides, so you can set the target repository once and issue multiple sub-commands without changing directories.

## Configuration

`repo-agent` uses **LiteLLM** to support hundreds of LLM providers. It is fully configurable via environment variables or a `.env` file at runtime.

### Core Settings

```ini
REPO_AGENT_REPO=/path/to/repo       # Target repository path
REPO_AGENT_COMMITS=10               # Number of commits to include in context
REPO_AGENT_INCLUDE_DIFF=0           # Set to 1 to include unstaged/staged diffs
REPO_AGENT_TIMEOUT=60               # HTTP request timeout in seconds
```

### LLM Provider Examples

#### 1. OpenAI (Default)
```ini
REPO_AGENT_PROVIDER=openai          # Default
REPO_AGENT_MODEL=gpt-4o-mini
REPO_AGENT_API_KEY=sk-...           # Or use OPENAI_API_KEY
```

#### 2. Anthropic
```ini
REPO_AGENT_PROVIDER=anthropic
REPO_AGENT_MODEL=claude-3-5-sonnet-20240620
REPO_AGENT_API_KEY=sk-ant-...
```

#### 3. Local Models (LM Studio, Ollama, vLLM)
For local servers, usually set the provider to `openai` and override the `API_BASE`.
```ini
REPO_AGENT_PROVIDER=openai
REPO_AGENT_API_BASE=http://localhost:1234/v1
REPO_AGENT_MODEL="qwen/qwen3-4b-thinking-2507"
```

### Custom Prompts

You can customize the agent's behavior by overriding its system prompts:

```ini
REPO_AGENT_SYSTEM_PROMPT="You are a senior developer..."  # Main chat system prompt
REPO_AGENT_PLAN_PROMPT="You are a git expert..."          # Planning agent prompt
REPO_AGENT_ANSWER_PROMPT="You are a helpful assistant..." # Answer generation prompt
```

## Usage

The following examples work whether you run `uv run repo-agent ...` from this directory or call the globally installed `repo-agent` binary. Add `--repo /path/to/repo` (or `-r`) when executing outside the target repository.

```bash
# Ask the configured LLM a question about the repo
repo-agent --repo ~/code/tiny-music-player ask "When was the auth refactor merged?"

# Ask while providing an explicit grep hint
repo-agent -r ~/code/tiny-music-player ask "Who implemented payment retries?" --grep "payment"

# Git helpers
repo-agent -r ~/code/tiny-music-player git status
repo-agent -r ~/code/tiny-music-player git pull origin main
repo-agent -r ~/code/tiny-music-player git push origin feature-branch
repo-agent -r ~/code/tiny-music-player git checkout -b spike/nemo-agent  # or use `git create-branch`

# Execute any shell command from the repo root
repo-agent -r ~/code/tiny-music-player shell "pytest -q"
```

### Natural-language Git agent

`repo-agent agent "..."` converts your prompt into a sequence of safe, read-only Git commands, executes them, and feeds the outputs back into the LLM before responding. The CLI automatically limits the command types (currently `log`, `show`, `rev-list`, `rev-parse`, `describe`, `status`, `shortlog`, `cat-file`, `diff`, `ls-tree`, `grep`, and `blame`) and shows every command/output block before presenting the final answer.

**Important:** Commands are executed directly, not via a shell. This means shell features like pipes (`|`), redirection (`>`), command substitution (`$(...)`), and environment variable expansion are **not** supported in the agent's plan.

### Example session

```
$ repo-agent -r ~/code/tiny-music-player ask "Find the commit that introduced rate limiting"
✔ Gathered repo context (branch main, 5 commits, status clean)
🤖 OpenAI: Commit 1f2c3d4 by Jane Doe on 2024-01-18 introduced the rate-limiting middleware.
```

## Testing

The repository ships with an integration-heavy pytest suite that clones [`martinmimigames/tiny-music-player`](https://github.com/martinmimigames/tiny-music-player) and runs the CLI against that checkout. The tests exercise every sub-command (branch creation, checkout, pull/push round-trips, shell execution, and the `ask` workflow). To execute the tests:

```bash
cd tools/repo-agent
uv run pytest
```

> **Note:** The tests require Git and outbound network access for the initial clone. Subsequent test cases operate on local bare remotes, so no further network access is needed.

## Extending

* Adjust `context_builder.py` to collect more repo signals (e.g., `git blame`, file diffs).
* Swap LLM providers by updating the environment variables outlined above.
* Add new Typer commands under `repo_agent.cli` for automation workflows.

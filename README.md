# 👁️ repo-lens

**Your repository's third eye.** 

Forget manually digging through git logs and grepping for context. `repo-lens` combines deep Git history analysis with advanced AI reasoning to give you instant clarity on your codebase. Whether you're hunting for the origin of a bug or summarizing years of commits, `repo-lens` sees what you might miss.

Powered by **smolagents** for iterative reasoning and **LiteLLM** for universal model support (OpenAI, Anthropic, Ollama, Qwen, and more).

---

### 🛠️ Prerequisites

Before you start peering into your repos, ensure you have:
- **Python 3.11** or higher.
- **Git** installed and available in your PATH.
- Access to an LLM provider:
    - **Cloud**: OpenAI, Anthropic, etc. (API Key required).
    - **Local**: LM Studio, Ollama, or vLLM (OpenAI-compatible server running).

---

### 🚀 Installation

Install `repo-lens` directly from this repository for the latest features:

```bash
# Using uv (recommended)
uv tool install repo-lens

# Using pip
pip install repo-lens
```

To build from source:
```bash
git clone https://github.com/satishjasthi/repo-lens.git
cd repo-lens
uv sync
```

---

### ⚙️ Getting Started

`repo-lens` is configured via environment variables or a `.env` file in your current directory.

Create a `.env` file:
```ini
# LLM Configuration
REPO_LENS_PROVIDER=openai               # openai, anthropic, ollama, etc.
REPO_LENS_MODEL=openai/gpt-oss-20b      # Your model identifier
REPO_LENS_API_BASE=http://localhost:1234/v1  # Base URL for local SLMs
REPO_LENS_API_KEY=sk-...                # Your API key (if needed)

# Repo Settings
REPO_LENS_REPO=/path/to/your/repo        # Optional defaults to current dir
REPO_LENS_TIMEOUT=60                     # HTTP timeout
```

---

### 🤖 Running the Agent

#### The `agent` command (Iterative Reasoning)
The `agent` command is the powerhouse of `repo-lens`. It doesn't just guess; it **reasons**. It plans Git commands, observes the results, and refines its search until it finds the answer.

```bash
repo-lens agent "Who added the bedrock support and what files did they change?"
```

#### The `ask` command (Quick Context)
For simple questions based on the recent history and current state:

```bash
repo-lens ask "Summarize the changes in the last 5 commits"
```

#### Thin Git Wrappers
`repo-lens` also includes thin wrappers for common Git tasks:
```bash
repo-lens git status
repo-lens git log --limit 5
repo-lens shell "ls -la"
```

---

### 📦 PyPI Publishing

Built with `uv`, `repo-lens` is ready for the world. To publish your own version:

1. Update `pyproject.toml` with your details.
2. Build the package:
   ```bash
   uv build
   ```
3. Publish to PyPI:
   ```bash
   uv publish
   ```

---

**Author:** [Satish Jasthi](https://github.com/satishjasthi)  
**License:** MIT

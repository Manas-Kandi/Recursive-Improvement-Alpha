# ✦ 9xf-code

A self-improving CLI coding agent powered by NVIDIA LLMs — or your own tiny local model. It plans, writes, and executes code to fulfill your prompts — and runs a background harness that analyzes every session to evolve its own prompts, tools, and strategies over time.

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the developer portal UI)
- **NVIDIA API key** — get one free at [build.nvidia.com](https://build.nvidia.com) *(only if using cloud models)*
- **Git**
- Optional: Docker (for sandboxed code execution)

## Quick Start

### Option A — No NVIDIA account needed (local model)

```bash
# 1. Clone
git clone https://github.com/Manas-Kandi/Recursive-Improvement-Alpha
cd Recursive-Improvement-Alpha

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install with local-model support
pip install -e ".[local]"

# 4. Initialize the database
siha init-db

# 5. Run the interactive menu and pick "Chat with local model"
siha
```

On first run the app auto-downloads a ~400 MB Qwen2.5-Coder-0.5B GGUF model to `~/.cache/siha/models`.

### Option B — With NVIDIA cloud model

```bash
# 1-2. Same clone & venv steps as above

# 3. Install the package
pip install -e .

# 4. Add your API key
cp .env.example .env
#    Open .env and set NVIDIA_API_KEY=<your key>

# 5. Initialize the database
siha init-db

# 6. Start chatting
siha chat
```

### Option C — With Ollama

If you already have [Ollama](https://ollama.com) installed with a coding model pulled:

```bash
ollama pull qwen2.5-coder:0.5b
siha chat --provider ollama
```

That's it. The `siha` command is available anywhere inside the activated venv.

---

## Commands

| Command | What it does |
|---|---|
| `siha chat` | Interactive coding session with full conversational context |
| `siha portal` | Launch the developer portal (backend + UI, auto-installs npm deps) |
| `siha bench` | Run the benchmark suite |
| `siha improve` | Manually trigger one self-improvement cycle |
| `siha init-db` | Create / migrate the SQLite database |

### Chat options
```bash
siha chat --model nvidia/llama-3.1-nemotron-ultra-253b-v1  # override model
siha chat --sandbox docker                                   # isolated execution
siha chat --workspace ~/my-project                          # set working directory
siha chat --provider local                                   # force local GGUF
siha chat --provider ollama                                  # force Ollama
```

Inside chat, type `clear` to reset conversational context, `exit` to quit.

### Developer Portal
```bash
siha portal
```
Opens the backend on **port 8000** and the React UI on **http://localhost:3000**.  
On first run, npm dependencies are installed automatically — no separate `npm install` needed.  
Auth token defaults to `dev` (set `PORTAL_DEV_TOKEN` in `.env` to change it).

---

## Configuration

All options live in `.env`:

| Variable | Default | Description |
|---|---|---|
| `NVIDIA_API_KEY` | — | Your NVIDIA API key (required for cloud provider) |
| `LLM_PROVIDER` | `auto` | `auto`, `nvidia`, `ollama`, or `local` |
| `AGENT_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b` | Model used for chat |
| `META_MODEL` | same | Model used for self-improvement analysis |
| `OLLAMA_URL` | `http://localhost:11434/v1` | Ollama OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | `qwen2.5-coder:0.5b` | Default Ollama model tag |
| `LOCAL_MODEL_REPO` | `Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF` | HuggingFace repo for in-process model |
| `LOCAL_MODEL_FILE` | `qwen2.5-coder-0.5b-instruct-q4_k_m.gguf` | GGUF filename to download |
| `PORTAL_DEV_TOKEN` | `dev` | Portal auth token |
| `SEARCH_API_KEY` | — | Tavily/Brave key (enables `web_search` tool) |
| `STEP_BUDGET` | `50` | Max agent steps per task |
| `TIMEOUT_S` | `120` | Tool execution timeout |
| `SANDBOX_DEFAULT` | `local` | `local` or `docker` |
| `REQUIRE_HUMAN_APPROVAL` | `false` | Gate self-improvement mutations behind manual approval |
| `IMPROVE_INTERVAL_S` | `300` | Background improvement cycle interval (seconds) |

---

## Architecture

```
src/siha/
├── agent/        # ReAct loop, prompts, session management
├── llm/          # Provider-agnostic LLM layer (NVIDIA, Ollama, local GGUF)
├── tools/        # Built-in tools, dynamic tool loading, registry
├── sandbox/      # Local + Docker execution environments
├── harness/      # Self-improvement: analyzer, mutator, evaluator, scheduler
├── benchmarks/   # Benchmark suite and trend tracking
├── portal/       # FastAPI backend (REST + SSE)
└── cli.py        # Typer CLI — entry point for all commands

portal-web/       # React + Vite frontend for the developer portal
```

## Self-Improvement Loop

1. After each task, the meta-model analyzes the execution trace
2. It proposes mutations to prompts, tools, or strategy parameters
3. Mutations are validated against the benchmark suite
4. Those that improve score by ≥ `BENCHMARK_PROMOTE_THRESHOLD` are auto-promoted
5. Regressions are automatically rolled back

## Testing

```bash
pip install -e ".[test]"
pytest
```

## License

MIT

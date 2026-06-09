# SIHA — Self-Improving Harness Agent

A self-improving CLI coding agent that works with **any** LLM — from 550B-parameter cloud models down to 7B local models — by making the **harness** (not the model) the brain. The architecture separates *decision-making* from *text generation* so small models can reliably execute multi-step coding tasks.

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the developer portal UI)
- **Git**
- Optional: [Ollama](https://ollama.com) (for Ollama-backed local models)
- Optional: `pip install -e ".[local]"` (for in-process tiny GGUF models — no external server needed)
- Optional: **NVIDIA API key** — get one free at [build.nvidia.com](https://build.nvidia.com) *(only needed for cloud models)*
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

On first run the app auto-downloads a ~400 MB Qwen2.5-Coder-0.5B GGUF model to `~/.cache/siha/models`. If you skip the `[local]` extra, the menu will still work but the in-process local option will be unavailable.

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
ollama pull qwen2.5-coder:7b      # 7B recommended for tool reliability
siha chat --provider ollama
```

That's it. The `siha` command is available anywhere inside the activated venv.

---

## Commands

| Command | What it does |
|---|---|
| `siha` | Interactive main menu — pick your provider and action |
| `siha chat` | Interactive coding session with full conversational context |
| `siha chat --provider local` | Chat using the in-process tiny model |
| `siha chat --provider ollama` | Chat using an Ollama server |
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
| `LOCAL_MODEL_CONTEXT_SIZE` | `4096` | Context window for the local model |
| `LOCAL_MODEL_N_THREADS` | `0` | CPU threads for local model (`0` = auto) |
| `PORTAL_DEV_TOKEN` | `dev` | Portal auth token |
| `SEARCH_API_KEY` | — | Tavily/Brave key (enables `web_search` tool) |
| `STEP_BUDGET` | `50` | Max agent steps per task |
| `TIMEOUT_S` | `120` | Tool execution timeout |
| `SANDBOX_DEFAULT` | `local` | `local` or `docker` |
| `REQUIRE_HUMAN_APPROVAL` | `true` | Gate self-improvement mutations behind manual approval |
| `IMPROVE_INTERVAL_S` | `300` | Background improvement cycle interval (seconds) |
| `BENCHMARK_RUNS` | `3` | Repetitions per benchmark when scoring a harness version (averaged) |
| `BENCHMARK_CACHE` | `true` | Reuse previously recorded scores for a harness version |
| `MAX_AUTO_BENCHMARKS` | `50` | Cap on auto-generated benchmarks |

---

## Architecture

### Harness-First Design Philosophy

**The problem:** Small models (7B parameters) are terrible at *decision-making* (when to use tools, which tool to use, how to format JSON) but fine at *text generation* (explaining, summarizing, formatting).

**The solution:** The harness makes all decisions. The model only generates natural language from pre-computed results.

```
User Input
    ↓
┌─────────────────┐
│  Intent Router  │  ← deterministic keywords (no LLM)
│  (0.5B or rules) │
└─────────────────┘
    ↓
┌─────────────────┐     Match?    ┌─────────────────┐
│  Action Mapper  │ ──yes────→    │  Execute Tools  │  ← deterministic
│ (DB templates,  │               └─────────────────┘
│  self-learned)  │                   ↓
└─────────────────┘               ┌─────────────────┐
    ↓ no match                     │  Main Model     │  ← only for natural
┌─────────────────┐                │  (summarizer)   │    language response
│  Task Planner   │  ← LLM plans   └─────────────────┘
│ (grammar-       │    first step       ↓ on success
│  constrained)   │               ┌─────────────────┐
└─────────────────┘               │  Synthesizer    │  ← distills the success
                                  │ (trace→template)│    into a NEW template
                                  └─────────────────┘
```

**The flywheel:** every novel request the LLM planner solves successfully is
deterministically generalized into an `ActionTemplate` (plus a regression
benchmark), evaluated as a candidate harness version, and promoted if it
doesn't regress. The harness gets faster and cheaper with use — LLM
involvement *decreases* over time.

### Core Modules

```
src/siha/
├── agent/
│   ├── loop.py          # ReAct loop with harness-first execution
│   ├── router.py        # Intent classifier (keyword + tiny LLM)
│   ├── action_mapper.py # Deterministic template → tool call mapping
│   ├── planner.py       # LLM fallback for novel requests
│   └── prompts.py       # Prompt management (DB-backed, versioned)
├── llm/
│   ├── factory.py       # Auto-detect provider (NVIDIA → Ollama → local)
│   ├── client.py        # NVIDIA client with retry logic
│   ├── ollama.py        # Ollama OpenAI-compatible wrapper
│   └── local_gguf.py    # In-process llama-cpp-python client
├── tools/
│   ├── base.py          # Tool ABC and result types
│   ├── builtin.py       # Built-in tools (run_python, write_file, etc.)
│   ├── registry.py      # Tool registry (builtin + dynamic DB tools)
│   └── dynamic.py       # Runtime tool loading from DB
├── sandbox/             # Local + Docker execution environments
├── harness/             # Self-improvement: analyzer, mutator, evaluator, scheduler
├── benchmarks/          # Benchmark suite and trend tracking
├── portal/              # FastAPI backend (REST + SSE streaming)
│   ├── routers/         # Modular routers (sessions, harness, mutations, etc.)
│   ├── auth.py          # Token-based auth middleware
│   └── events.py        # Per-subscriber event bus for SSE
└── cli.py               # Typer CLI — thin entry point

portal-web/               # React + Vite + Tailwind frontend
```

### How It Works (with a 7B model)

**Example:** `create a new folder called "test-run-2" and within that folder create an Index.html file with hello world`

1. **Intent Router** sees `create` + `folder` → classifies as `tool_call` (deterministic, no LLM)
2. **Action Mapper** scans the prompt with regex templates:
   - Match 1: `folder called "test-run-2"` → `run_shell("mkdir -p test-run-2")`
   - Match 2: `create an Index.html file with hello world` → `write_file("index.html", "hello world")`
3. **Path Resolution** sees bare filename `index.html` after a folder was created → resolves to `test-run-2/index.html`
4. **Both tools execute** sequentially before the model even responds
5. **Main model** receives: "Folder created. File written." → generates: "Done!" (no decision needed)

---

## Decision Log

### 2026-06-09 — Learnable Template Layer, Grammar-Constrained Planning, Trustworthy Evaluation

**Context:** The self-improvement loop could mutate prompts/tools but not the
template layer (the actual product); benchmark scoring trusted logged output
instead of the filesystem; promotion decisions were single-run and noisy; the
meta-critic required a cloud model for every trace.

**What changed:**
- **M1 — Learnable templates:** `ActionTemplate` DB model + `MutationKind.template`
  with full propose/candidate/promote/rollback lifecycle and `HarnessVersion.template_set`
  pinning. `ActionMapper` loads templates from the DB with priority-ordered,
  span-claiming matching (fixes overlapping duplicate tool calls). New
  `TemplateSynthesizer` deterministically distills successful LLM-planned tasks
  into reusable templates — the self-improvement flywheel.
- **M2 — Reliability & safety:** `tools/safety.py` command guard blocks
  catastrophic shell commands (rm -rf /, sudo, mkfs, fork bombs, curl|sh…).
  `llm/grammar.py` generates GBNF grammars from tool schemas;
  `LocalGGUFClient.chat_constrained` makes malformed tool calls physically
  impossible for the local provider.
- **M3 — Trustworthy evaluation:** benchmark `file_checks` verify the real
  workspace filesystem; each benchmark runs `BENCHMARK_RUNS` times with score
  caching per harness version; the auto-benchmark generator deduplicates by
  prompt similarity instead of capping one-per-category; every synthesized
  template ships with its own regression benchmark.
- **M4 — Local-first meta-critic:** `harness/triage.py` classifies healthy
  traces and recognizable failure modes (missing path, safety block, unknown
  tool, timeout, malformed output, step-budget exhaustion) deterministically;
  the LLM analyzer is only consulted for unexplained traces and its client is
  lazily constructed. `REQUIRE_HUMAN_APPROVAL` now defaults to `true`.
- **M5 — Grounded context:** `agent/workspace_index.py` injects a compact
  file-tree snapshot into the system prompt; `agent/scaffolds.py` expands
  trivial content into proper documents ("hello world" → real HTML5 page).

### 2025-06-08 — Harness-First Architecture for Small Model Support

**Context:** User tested the agent with `qwen2.5-coder:7b` via Ollama. The model repeatedly said "I can't do that" or gave instructions instead of using tools. The root cause: small models (7B) lack the reasoning capacity for reliable ReAct tool-calling.

**Decision:** Redesign the agent loop so the **harness** (not the model) decides what to do.

**What changed:**
- New `src/siha/agent/router.py` — IntentRouter classifies user input into `chat`, `tool_call`, `code_generation`, `analysis` using keyword-based rules first, tiny LLM second
- New `src/siha/agent/action_mapper.py` — ActionMapper maps common request patterns directly to tool calls via deterministic regex templates (no LLM involved)
- New `src/siha/agent/planner.py` — TaskPlanner is an LLM-based fallback for novel requests that don't match any template
- Updated `src/siha/agent/loop.py` — AgentLoop now executes ActionMapper steps BEFORE the main model responds; the model only sees completed tool results
- Added `working_memory` to AgentLoop — tracks recent actions (created folders, written files) so follow-up requests have context; `_resolve_path()` prepends the last folder to bare filenames
- Updated `src/siha/llm/ollama.py` — OllamaClient no longer passes `tools` to the API (Qwen enters forced function-calling mode when `tools` is present, outputting JSON even for greetings)
- Updated `src/siha/agent/loop.py` `_get_system_prompt()` — simplified system prompt; removed "for greetings, don't use tools" guidance because the router already handles that separation

**Tests:** All 33 pytest tests pass after each commit.

**Pros:**
- Common tasks (`create folder`, `write file`, `move file`, `run code`) work with 7B models
- Compound requests (`create folder X and write file Y`) execute multiple steps automatically
- Deterministic path means no hallucination of tool calls
- Fast — keyword matching is microseconds; no LLM latency for common tasks

**Cons:**
- Templates must be explicitly added for each new pattern (maintenance burden)
- Novel requests still fall back to LLM planner, which may fail with small models
- Path resolution is simplistic (only remembers last created folder)
- Content generation is literal ("write index.html with hello world" writes literal text, not HTML)

**Commits:** `9c09d06` → `f179688` → `332bb86` → `8b7158b` → `debf997` → `aa5f218` → `132a53b` → `9218af8` → `bcebcdb` → `0ae20d1`

### 2025-06-07 — Phase 4: Product Polish (Portal UI/UX)

**Context:** The frontend portal needed authentication, better mutation viewing, benchmark drilldown, version comparison, and system health monitoring.

**What changed:**
- New `portal-web/src/AuthContext.tsx` — React Context for token management (localStorage)
- New `portal-web/src/pages/Login.tsx` — Login page with backend token verification
- New `portal-web/src/pages/Versions.tsx` — Harness version comparison with side-by-side diff
- New `portal-web/src/pages/Health.tsx` — System health dashboard (API connectivity, token status)
- Updated `portal-web/src/pages/Mutations.tsx` — Collapsible diff viewer with color-coded before/after panels
- Updated `portal-web/src/pages/Benchmarks.tsx` — "Run All" button with per-benchmark PASS/FAIL drilldown
- Updated `portal-web/src/App.tsx` — AuthProvider wrapper, auth guard, new routes, Sign Out button
- Updated `portal-web/src/api.ts` — Dynamic token from localStorage, 401/403 interceptor with auto-logout

**Tests:** TypeScript compiles without errors (`tsc --noEmit`). Vite build succeeds. All 33 Python tests pass.

**Commit:** `ecce4d3`

### 2025-06-07 — Fix Ollama/Qwen Tool Calling

**Context:** Qwen models via Ollama's OpenAI-compatible endpoint output raw JSON in content instead of using `tool_calls`.

**What changed:**
- OllamaClient no longer passes `tools` to the API to avoid forced function-calling mode
- Added `_try_parse_content_tool_call()` to extract JSON tool calls from raw model output
- Content parser regex now matches both `"tool"` and `"name"` keys
- Strengthened system prompt with explicit rules and few-shot example

**Commit:** `f179688`

### 2025-06-07 — Phase 3: Observability Improvements

**What changed:**
- Per-subscriber `asyncio.Queue` event bus (`src/siha/portal/events.py`)
- Structured JSON logging (`src/siha/logging.py`)
- Task categorization (`user`, `benchmark`, `system`) + trace IDs across agent, tools, scheduler, portal
- Alembic migration for `category` and `trace_id` columns on `Task` model

**Commit:** `d32c42b`

### 2025-06-07 — Phase 2: Maintainability Improvements

**What changed:**
- Split `cli.py` into `cli.py` (entry point), `cli_commands.py` (command implementations), `cli_display.py` (rich display)
- Split `portal/api.py` into modular routers (`sessions`, `harness`, `mutations`, `benchmarks`, `tools`, `run`, `stream`)
- Added Pydantic schemas (`src/siha/schemas.py`) for API validation
- Added typed frontend API layer (`portal-web/src/api.ts`, `portal-web/src/types.ts`)

**Commit:** `e720569`

### 2025-06-07 — Phase 1: Safety and Correctness

**What changed:**
- Initial safety and correctness improvements to the core agent loop

**Commit:** `659ac51`

---

## Testing

```bash
pip install -e ".[test,local]"
pytest
```

**Test suite coverage:**
- `test_db.py` — Database models and session management
- `test_benchmarks.py` — Benchmark execution and scoring
- `test_dynamic_tools.py` — Dynamic tool loading and execution
- `test_mutation_lifecycle.py` — Mutation approval, evaluation, promotion, rollback
- `test_action_templates.py` — Template matching, DB lifecycle, version pinning, synthesis
- `test_safety_and_grammar.py` — Shell command guard and GBNF grammar generation
- `test_evaluation.py` — Filesystem-grounded scoring, evaluator caching, generator dedupe
- `test_triage.py` — Rule-based trace triage taxonomy
- `test_scaffolds_and_index.py` — Content scaffolds and workspace index

---

## License

MIT

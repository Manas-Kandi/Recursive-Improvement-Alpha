# Self-Improving Harness (SIHA)

A Python CLI coding agent powered by switchable NVIDIA LLMs that plans, writes, and executes code to fulfill user prompts, while a background self-improvement harness analyzes every run to evolve its own prompts, tool library, execution strategy, and benchmarks.

## Features

- **Multi-model support**: NVIDIA Nemotron-3, Kimi-K2.6, Gemma-3N
- **Auto-discovery**: Automatically discovers and validates new tools
- **Self-improvement**: Analyzes runs to improve prompts, tools, and strategies
- **Benchmark-driven**: All improvements validated against benchmark suite
- **Developer portal**: FastAPI + React dashboard for monitoring
- **Sandbox execution**: Safe code execution in isolated environments
- **Version control**: Full audit trail with rollback capability

## Quick Start

### Prerequisites

- Python 3.11+
- NVIDIA API key (get from [NVIDIA NGC](https://catalog.ngc.nvidia.com/))
- Optional: Docker (for containerized sandbox)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Self-Improving-Harness
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your NVIDIA_API_KEY
```

5. Initialize database:
```bash
siha init-db
```

### Usage

#### Interactive Chat
```bash
siha chat
```
Options:
- `--model` or `-m`: Select model (default: nvidia/nemotron-3-ultra-550b-a55b)
- `--sandbox` or `-s`: Sandbox mode (local|docker, default: local)

#### Run Benchmarks
```bash
siha bench
```

#### Trigger Self-Improvement
```bash
siha improve
```

#### Launch Developer Portal
```bash
siha portal
```
Then open http://localhost:8000 in your browser. Use the token from `.env` for authentication.

### Portal Frontend

The React frontend is in `portal-web/`:

```bash
cd portal-web
npm install
npm run dev
```

The frontend will be available at http://localhost:3000.

## Architecture

### Core Components

- **LLM Client** (`src/siha/llm/`): NVIDIA API wrapper with streaming support
- **Agent Loop** (`src/siha/agent/`): ReAct-style planning and execution
- **Tool Framework** (`src/siha/tools/`): Extensible tool system with auto-discovery
- **Sandbox** (`src/siha/sandbox/`): Isolated execution environments
- **Harness** (`src/siha/harness/`): Self-improvement analysis and mutation
- **Benchmarks** (`src/siha/benchmarks/`): Test suite and trend tracking
- **Portal** (`src/siha/portal/`): FastAPI backend + React frontend

### Data Model

- **Task**: User prompts and execution results
- **Step**: Individual agent actions (plan, tool_call, observation)
- **Tool**: Available tools with implementations
- **Prompt**: System prompts for different roles
- **Strategy**: Configuration parameters
- **Mutation**: Proposed and applied changes
- **Benchmark**: Test specifications
- **HarnessVersion**: Snapshots for rollback

## Self-Improvement Process

1. **Analysis**: After each task, the meta LLM analyzes the execution trace
2. **Proposal**: Mutations are proposed for prompts, tools, or strategies
3. **Validation**: Mutations are tested against the benchmark suite
4. **Promotion**: Improvements that meet the threshold are auto-promoted
5. **Rollback**: Regressions are automatically reverted

## Configuration

Environment variables in `.env`:

- `NVIDIA_API_KEY`: Required NVIDIA API key
- `SEARCH_API_KEY`: Optional Tavily API key enabling the `web_search` tool
- `PORTAL_DEV_TOKEN`: Portal authentication token (default: dev)
- `REQUIRE_HUMAN_APPROVAL`: Force manual approval (default: false)
- `IMPROVE_INTERVAL_S`: Background improvement interval (default: 300)
- `BENCHMARK_PROMOTE_THRESHOLD`: Improvement threshold (default: 0.05)
- `STEP_BUDGET`: Max agent steps per task (default: 50)
- `TIMEOUT_S`: Execution timeout (default: 120)
- `SANDBOX_DEFAULT`: Default sandbox mode (default: local)

## Testing

Run tests:
```bash
pip install -e ".[test]"
pytest
```

## Development

### Adding New Tools

1. Create a tool class inheriting from `Tool` in `src/siha/tools/builtin.py`
2. Implement `name`, `description`, `parameters`, and `run` methods
3. Add to `BUILTIN_TOOLS` list

### Adding Benchmarks

Edit `src/siha/benchmarks/runner.py` and add to the `benchmarks` list in `seed_benchmarks()`.

## License

MIT License

## Contributing

Contributions welcome! Please read the architecture documentation in `.windsurf/plans/` before making changes.

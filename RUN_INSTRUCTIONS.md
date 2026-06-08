# SIHA Run Instructions

This document provides comprehensive step-by-step instructions for running the SIHA (Self-Improving Harness) system in two modes:
1. **Terminal Agent**: Interactive CLI chat with the coding agent
2. **Developer Portal**: Full-featured web dashboard with frontend and backend

---

## Prerequisites

Before running SIHA, ensure you have the following installed:

- **Python 3.11+** (Check with `python3 --version`)
- **Node.js 18+** (Check with `node --version`)
- **npm** (Check with `npm --version`)
- **NVIDIA API Key** (Get from [NVIDIA NGC](https://catalog.ngc.nvidia.com/))

---

## Initial Setup (One-Time)

These steps only need to be done once on your machine.

### Step 1: Navigate to the Project Directory

```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness
```

### Step 2: Create and Activate Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

**Note**: Your terminal prompt should now show `(venv)` at the beginning, indicating the virtual environment is active.

### Step 3: Install Python Dependencies

```bash
pip install -e .
```

This installs SIHA in editable mode along with all required Python packages.

### Step 4: Configure Environment Variables

```bash
cp .env.example .env
```

Then edit the `.env` file to add your NVIDIA API key:

```bash
nano .env  # or use your preferred editor
```

Add or update this line:
```
NVIDIA_API_KEY=your_actual_nvidia_api_key_here
```

Save and exit (in nano: Ctrl+X, then Y, then Enter).

### Step 5: Initialize the Database

```bash
siha init-db
```

This creates the SQLite database and seeds default prompts.

### Step 6: Install Frontend Dependencies (One-Time)

```bash
cd portal-web
npm install
cd ..
```

This installs all Node.js dependencies for the React frontend.

---

## Running the Terminal Agent

Open **Terminal 1** and follow these steps:

### Step 1: Activate Virtual Environment

```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness
source venv/bin/activate
```

### Step 2: Run the Interactive Chat

```bash
siha chat
```

**Optional Flags**:
- `--model` or `-m`: Select a different model (default: nvidia/nemotron-3-ultra-550b-a55b)
  ```bash
  siha chat --model nvidia/kimi-k2-6b-a55b
  ```
- `--sandbox` or `-s`: Choose sandbox mode (default: local)
  ```bash
  siha chat --sandbox docker
  ```
- `--workspace` or `-w`: Specify workspace directory (default: current directory)
  ```bash
  siha chat --workspace /path/to/your/project
  ```

### Step 3: Interact with the Agent

Once running, you'll see a welcome panel. Type your coding tasks as natural language prompts:

```
You: Create a Python function that calculates fibonacci numbers
```

The agent will:
1. Think about the task
2. Plan the approach
3. Write code using available tools
4. Execute and test the code
5. Provide the final answer

**Useful Commands**:
- Type `exit` or `quit` to close the agent
- Type `clear` to clear conversation context
- Press Ctrl+C to interrupt a running task

---

## Running the Developer Portal

The developer portal requires **two separate terminals** - one for the backend API and one for the frontend.

### Terminal 1: Backend API (FastAPI)

Open **Terminal 1** and follow these steps:

#### Step 1: Activate Virtual Environment

```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness
source venv/bin/activate
```

#### Step 2: Start the Backend Server

```bash
python -m uvicorn siha.portal.api:app --host 0.0.0.0 --port 8000 --log-level warning
```

**What this does**:
- Starts the FastAPI backend server
- Listens on all network interfaces (0.0.0.0)
- Runs on port 8000
- Uses warning log level to reduce noise

**Expected Output**:
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Backend URLs**:
- API Base: http://localhost:8000
- API Documentation (Swagger UI): http://localhost:8000/docs
- OpenAPI Schema: http://localhost:8000/openapi.json

**Keep this terminal open** - the backend must remain running.

---

### Terminal 2: Frontend (Vite + React)

Open **Terminal 2** (new terminal window/tab) and follow these steps:

#### Step 1: Navigate to Frontend Directory

```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness/portal-web
```

#### Step 2: Start the Frontend Dev Server

```bash
npm run dev
```

**What this does**:
- Starts the Vite development server
- Runs on port 3000 by default
- Enables hot module replacement (HMR)
- Proxies `/api` requests to the backend on port 8000

**Expected Output**:
```
VITE v5.4.21  ready in 1254 ms

➜  Local:   http://localhost:3000/
➜  Network: use --host to expose
➜  press h + enter to show help
```

**Frontend URL**:
- Developer Portal: http://localhost:3000

**Keep this terminal open** - the frontend must remain running.

---

## Accessing the Developer Portal

Once both terminals are running:

1. Open your web browser
2. Navigate to: **http://localhost:3000**
3. You should see the SIHA Developer Portal dashboard

**Authentication**:
- The portal requires an auth token
- Check your `.env` file for `PORTAL_DEV_TOKEN` (default: `dev`)
- When making API calls, include the header: `Authorization: Bearer dev`

**Portal Features**:
- View recent agent sessions and execution traces
- Monitor live agent activity via SSE streaming
- Browse and manage harness state (prompts, tools, strategies)
- View benchmark trends and performance metrics
- Review and approve/reject pending mutations
- Manually trigger improvement cycles

---

## Alternative: Single Command for Portal

The SIHA CLI provides a convenience command that starts both frontend and backend automatically:

```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness
source venv/bin/activate
siha portal
```

**What this does**:
1. Checks if `node_modules/vite` exists; if not, runs `npm install` automatically
2. Starts `npm run dev` as a background subprocess (Vite on port 3000)
3. Registers cleanup so Ctrl+C kills both processes
4. Prints a panel pointing to http://localhost:3000
5. Starts uvicorn on port 8000 at warning log level

**Advantages**:
- One command to start everything
- Automatic cleanup on exit
- First-time setup handled automatically

**Disadvantages**:
- Both servers run in the same terminal (harder to see separate logs)
- Less control over individual server configuration

---

## Stopping the Services

### Stopping Terminal Agent

In the terminal running `siha chat`:
- Type `exit` and press Enter, or
- Press Ctrl+C

### Stopping Developer Portal (Two-Terminal Setup)

**Terminal 1 (Backend)**: Press Ctrl+C
**Terminal 2 (Frontend)**: Press Ctrl+C

### Stopping Developer Portal (Single Command)

In the terminal running `siha portal`:
- Press Ctrl+C (this will stop both backend and frontend)

---

## Troubleshooting

### Issue: "command not found: python"

**Solution**: Use `python3` instead of `python`:
```bash
python3 -m uvicorn siha.portal.api:app --host 0.0.0.0 --port 8000 --log-level warning
```

### Issue: "ModuleNotFoundError: No module named 'siha'"

**Solution**: Make sure you've activated the virtual environment and installed in editable mode:
```bash
source venv/bin/activate
pip install -e .
```

### Issue: Frontend shows "Connection Refused" or API errors

**Solution**: Ensure the backend is running on port 8000:
```bash
curl http://localhost:8000/docs
```
If this fails, check Terminal 1 for backend errors.

### Issue: Port already in use (3000 or 8000)

**Solution**: Find and kill the process using the port:
```bash
# For port 3000
lsof -ti:3000 | xargs kill -9

# For port 8000
lsof -ti:8000 | xargs kill -9
```

### Issue: NVIDIA API authentication errors

**Solution**: Verify your `.env` file has the correct `NVIDIA_API_KEY`:
```bash
cat .env | grep NVIDIA_API_KEY
```

### Issue: Database errors

**Solution**: Re-initialize the database:
```bash
siha init-db
```

### Issue: Frontend dependencies missing

**Solution**: Reinstall npm dependencies:
```bash
cd portal-web
rm -rf node_modules package-lock.json
npm install
```

---

## Quick Reference

### Terminal Agent (Single Terminal)
```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness
source venv/bin/activate
siha chat
```

### Developer Portal (Two Terminals)

**Terminal 1 - Backend:**
```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness
source venv/bin/activate
python -m uvicorn siha.portal.api:app --host 0.0.0.0 --port 8000 --log-level warning
```

**Terminal 2 - Frontend:**
```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness/portal-web
npm run dev
```

### Developer Portal (Single Terminal)
```bash
cd /Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness
source venv/bin/activate
siha portal
```

---

## Environment Variables Reference

Key environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `NVIDIA_API_KEY` | NVIDIA NGC API key (required) | - |
| `PORTAL_DEV_TOKEN` | Portal authentication token | `dev` |
| `REQUIRE_HUMAN_APPROVAL` | Force manual approval for mutations | `false` |
| `IMPROVE_INTERVAL_S` | Background improvement interval (seconds) | `300` |
| `BENCHMARK_PROMOTE_THRESHOLD` | Improvement threshold for auto-promotion | `0.05` |
| `STEP_BUDGET` | Max agent steps per task | `50` |
| `TIMEOUT_S` | Execution timeout (seconds) | `120` |
| `SANDBOX_DEFAULT` | Default sandbox mode (local/docker) | `local` |

---

## Additional Commands

### Run Benchmarks
```bash
siha bench
```

### Trigger Self-Improvement Manually
```bash
siha improve
```

### Re-initialize Database
```bash
siha init-db
```

---

## Support

For issues or questions:
- Check the main README.md for architecture details
- Review API documentation at http://localhost:8000/docs when backend is running
- Check terminal logs for error messages

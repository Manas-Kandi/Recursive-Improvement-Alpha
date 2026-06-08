"""FastAPI backend with REST + SSE + auth"""

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from typing import List, Optional
from siha.db import get_session
from siha.models import Task, Step, ToolCall, Tool, Prompt, Strategy, Mutation, Benchmark, BenchmarkRun, HarnessVersion
from siha.benchmarks.runner import get_benchmark_trend
from siha.config import settings
from siha.portal.events import event_bus
import json


app = FastAPI(title="9xf-code Portal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background self-improvement scheduler (started on app startup).
_scheduler = None


@app.on_event("startup")
def _start_scheduler():
    """Start the background improvement scheduler when the portal boots."""
    global _scheduler
    from siha.harness.scheduler import Scheduler

    _scheduler = Scheduler()
    _scheduler.start()


@app.on_event("shutdown")
def _stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.stop()


def verify_auth(authorization: Optional[str] = Header(None)):
    """Verify authorization token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization.replace("Bearer ", "")
    if token != settings.portal_dev_token:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    return token


@app.get("/sessions")
def get_sessions(limit: int = 50, token: str = Depends(verify_auth)):
    """Get list of recent sessions (tasks)"""
    with get_session() as session:
        tasks = session.query(Task).order_by(Task.id.desc()).limit(limit).all()
        return [
            {
                "id": t.id,
                "prompt": t.user_prompt,
                "model": t.model,
                "status": t.status,
                "duration_ms": t.duration_ms,
                "ts": t.ts.isoformat()
            }
            for t in tasks
        ]


@app.get("/sessions/{session_id}")
def get_session_detail(session_id: int, token: str = Depends(verify_auth)):
    """Get detailed session trace"""
    with get_session() as session:
        task = session.get(Task, session_id)
        if not task:
            raise HTTPException(status_code=404, detail="Session not found")
        
        steps = session.query(Step).filter(Step.task_id == session_id).order_by(Step.idx).all()
        tool_calls = session.query(ToolCall).filter(ToolCall.task_id == session_id).all()
        
        return {
            "task": {
                "id": task.id,
                "prompt": task.user_prompt,
                "model": task.model,
                "status": task.status,
                "duration_ms": task.duration_ms,
                "sandbox_mode": task.sandbox_mode,
                "error_summary": task.error_summary,
                "ts": task.ts.isoformat()
            },
            "steps": [
                {
                    "id": s.id,
                    "idx": s.idx,
                    "type": s.type,
                    "content": s.content,
                    "tokens": s.tokens,
                    "latency_ms": s.latency_ms
                }
                for s in steps
            ],
            "tool_calls": [
                {
                    "id": tc.id,
                    "tool_id": tc.tool_id,
                    "args": tc.args,
                    "result": tc.result,
                    "success": tc.success,
                    "duration_ms": tc.duration_ms
                }
                for tc in tool_calls
            ]
        }


@app.get("/stream/logs")
async def stream_logs(token: str = Depends(verify_auth)):
    """SSE stream of live logs"""
    async def event_generator():
        while True:
            event = await event_bus.get_event()
            yield event
    
    return EventSourceResponse(event_generator())


@app.get("/harness/state")
def get_harness_state(token: str = Depends(verify_auth)):
    """Get current harness state (active prompts, tools, strategies)"""
    with get_session() as session:
        from siha.models import PromptStatus, ToolStatus, StrategyStatus
        
        prompts = session.query(Prompt).filter(Prompt.status == PromptStatus.active).all()
        tools = session.query(Tool).filter(Tool.status == ToolStatus.active).all()
        strategies = session.query(Strategy).filter(Strategy.status == StrategyStatus.active).all()
        
        return {
            "prompts": [
                {"id": p.id, "role": p.role, "version": p.version, "text": p.text}
                for p in prompts
            ],
            "tools": [
                {"id": t.id, "name": t.name, "version": t.version, "description": t.description}
                for t in tools
            ],
            "strategies": [
                {"id": s.id, "key": s.key, "value": s.value, "version": s.version}
                for s in strategies
            ]
        }


@app.get("/harness/versions")
def get_harness_versions(token: str = Depends(verify_auth)):
    """Get all harness versions"""
    with get_session() as session:
        versions = session.query(HarnessVersion).order_by(HarnessVersion.id.desc()).all()
        return [
            {
                "id": v.id,
                "label": v.label,
                "ts": v.ts.isoformat(),
                "prompt_count": len(v.prompt_set),
                "tool_count": len(v.tool_set),
                "strategy_count": len(v.strategy_set)
            }
            for v in versions
        ]


@app.get("/harness/versions/{a}/diff/{b}")
def diff_versions(a: int, b: int, token: str = Depends(verify_auth)):
    """Get diff between two harness versions"""
    with get_session() as session:
        version_a = session.get(HarnessVersion, a)
        version_b = session.get(HarnessVersion, b)
        
        if not version_a or not version_b:
            raise HTTPException(status_code=404, detail="Version not found")
        
        return {
            "version_a": {
                "id": version_a.id,
                "label": version_a.label,
                "prompts": version_a.prompt_set,
                "tools": version_a.tool_set,
                "strategies": version_a.strategy_set
            },
            "version_b": {
                "id": version_b.id,
                "label": version_b.label,
                "prompts": version_b.prompt_set,
                "tools": version_b.tool_set,
                "strategies": version_b.strategy_set
            }
        }


@app.get("/mutations")
def get_mutations(token: str = Depends(verify_auth)):
    """Get mutation history"""
    with get_session() as session:
        mutations = session.query(Mutation).order_by(Mutation.id.desc()).limit(100).all()
        return [
            {
                "id": m.id,
                "kind": m.kind,
                "target_id": m.target_id,
                "before": m.before,
                "after": m.after,
                "rationale": m.rationale,
                "status": m.status,
                "benchmark_delta": m.benchmark_delta,
                "created_ts": m.created_ts.isoformat(),
                "decided_ts": m.decided_ts.isoformat() if m.decided_ts else None
            }
            for m in mutations
        ]


@app.post("/mutations/{mutation_id}/approve")
def approve_mutation(mutation_id: int, token: str = Depends(verify_auth)):
    """Approve a pending mutation"""
    from siha.harness.mutator import Mutator
    
    with get_session() as session:
        mutation = session.get(Mutation, mutation_id)
        if not mutation:
            raise HTTPException(status_code=404, detail="Mutation not found")
        
        if mutation.status != "pending":
            raise HTTPException(status_code=400, detail="Mutation not pending")
        
        mutator = Mutator()
        mutator.apply_mutation(mutation)
        
        return {"status": "approved"}


@app.post("/mutations/{mutation_id}/reject")
def reject_mutation(mutation_id: int, token: str = Depends(verify_auth)):
    """Reject a pending mutation"""
    with get_session() as session:
        mutation = session.get(Mutation, mutation_id)
        if not mutation:
            raise HTTPException(status_code=404, detail="Mutation not found")
        
        if mutation.status != "pending":
            raise HTTPException(status_code=400, detail="Mutation not pending")
        
        from siha.models import MutationStatus
        mutation.status = MutationStatus.rejected
        session.commit()
        
        return {"status": "rejected"}


@app.get("/benchmarks")
def get_benchmarks(token: str = Depends(verify_auth)):
    """Get all benchmarks"""
    with get_session() as session:
        benchmarks = session.query(Benchmark).all()
        return [
            {
                "id": b.id,
                "name": b.name,
                "category": b.category,
                "origin": b.origin,
                "created_ts": b.created_ts.isoformat()
            }
            for b in benchmarks
        ]


@app.get("/benchmarks/trend")
def get_benchmark_trend_endpoint(token: str = Depends(verify_auth)):
    """Get benchmark trend data"""
    return get_benchmark_trend()


@app.post("/improve")
def trigger_improve(token: str = Depends(verify_auth)):
    """Manually trigger an improvement cycle (analyze + evaluate)."""
    from siha.harness.scheduler import Scheduler

    Scheduler().trigger_improvement()
    return {"status": "triggered"}


@app.post("/run")
def run_task(payload: dict, token: str = Depends(verify_auth)):
    """Run a coding task through the agent and return the resulting task id."""
    from siha.agent.loop import AgentLoop

    prompt = (payload or {}).get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing 'prompt'")

    sandbox = (payload or {}).get("sandbox", settings.sandbox_default)
    model = (payload or {}).get("model")

    agent = AgentLoop(model)
    task = agent.run(prompt, sandbox_mode=sandbox)
    return {
        "id": task.id,
        "status": task.status,
        "duration_ms": task.duration_ms,
        "final_answer": task.final_answer,
        "error_summary": task.error_summary,
    }


@app.get("/tools")
def get_tools(token: str = Depends(verify_auth)):
    """Get all tools"""
    with get_session() as session:
        tools = session.query(Tool).all()
        return [
            {
                "id": t.id,
                "name": t.name,
                "version": t.version,
                "description": t.description,
                "status": t.status,
                "implementation_kind": t.implementation_kind,
                "source_url": t.source_url,
                "created_ts": t.created_ts.isoformat()
            }
            for t in tools
        ]

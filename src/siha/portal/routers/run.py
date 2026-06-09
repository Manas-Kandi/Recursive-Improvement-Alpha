"""Task execution endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from siha.config import settings
from siha.agent.loop import AgentLoop
from siha.portal.auth import verify_auth
from siha.schemas import RunTaskPayload, RunTaskResponse

router = APIRouter(tags=["run"])


@router.post("/run", response_model=RunTaskResponse)
def run_task(payload: RunTaskPayload, token: str = Depends(verify_auth)):
    """Run a coding task through the agent and return the resulting task id."""
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing 'prompt'")

    sandbox = payload.sandbox or settings.sandbox_default
    model = payload.model
    provider = payload.provider
    harness_version_id = payload.harness_version_id
    trace_id = payload.trace_id

    agent = AgentLoop(model=model, provider=provider, harness_version_id=harness_version_id)
    task = agent.run(
        prompt,
        sandbox_mode=sandbox,
        trace_id=trace_id,
    )
    return RunTaskResponse(
        id=task.id,
        status=task.status,
        duration_ms=task.duration_ms,
        final_answer=task.final_answer,
        error_summary=task.error_summary,
        trace_id=task.trace_id,
    )

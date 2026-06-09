"""Self-improvement trigger endpoint."""

from fastapi import APIRouter, Depends

from siha.portal.auth import verify_auth
from siha.schemas import ImprovementTriggerResponse

router = APIRouter(tags=["improve"])


@router.post("/improve", response_model=ImprovementTriggerResponse)
def trigger_improvement(token: str = Depends(verify_auth)):
    """Manually trigger one self-improvement cycle."""
    from siha.harness.scheduler import Scheduler

    scheduler = Scheduler()
    scheduler.trigger_improvement()
    return ImprovementTriggerResponse(status="ok")

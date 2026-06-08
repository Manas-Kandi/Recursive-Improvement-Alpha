"""Session/task endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from siha.db import get_session
from siha.models import Task, Step, ToolCall
from siha.portal.auth import verify_auth
from siha.schemas import SessionListItem, SessionDetail

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=List[SessionListItem])
def get_sessions(limit: int = 50, token: str = Depends(verify_auth)):
    """Get list of recent sessions (tasks)."""
    with get_session() as session:
        tasks = session.query(Task).order_by(Task.id.desc()).limit(limit).all()
        return [
            SessionListItem(
                id=t.id,
                prompt=t.user_prompt,
                model=t.model,
                status=t.status,
                duration_ms=t.duration_ms,
                ts=t.ts.isoformat(),
            )
            for t in tasks
        ]


@router.get("/{session_id}", response_model=SessionDetail)
def get_session_detail(session_id: int, token: str = Depends(verify_auth)):
    """Get detailed session trace."""
    with get_session() as session:
        task = session.get(Task, session_id)
        if not task:
            raise HTTPException(status_code=404, detail="Session not found")

        steps = session.query(Step).filter(Step.task_id == session_id).order_by(Step.idx).all()
        tool_calls = session.query(ToolCall).filter(ToolCall.task_id == session_id).all()

        return SessionDetail(
            task={
                "id": task.id,
                "prompt": task.user_prompt,
                "model": task.model,
                "status": task.status,
                "duration_ms": task.duration_ms,
                "sandbox_mode": task.sandbox_mode,
                "error_summary": task.error_summary,
                "ts": task.ts.isoformat(),
            },
            steps=[
                {
                    "id": s.id,
                    "idx": s.idx,
                    "type": s.type,
                    "content": s.content,
                    "tokens": s.tokens,
                    "latency_ms": s.latency_ms,
                }
                for s in steps
            ],
            tool_calls=[
                {
                    "id": tc.id,
                    "tool_id": tc.tool_id,
                    "args": tc.args,
                    "result": tc.result,
                    "success": tc.success,
                    "duration_ms": tc.duration_ms,
                }
                for tc in tool_calls
            ],
        )

"""Harness state and version endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from siha.db import get_session
from siha.models import Prompt, PromptStatus, Tool, ToolStatus, Strategy, StrategyStatus, HarnessVersion
from siha.portal.auth import verify_auth
from siha.schemas import HarnessState, HarnessVersionItem, VersionDiffResponse

router = APIRouter(prefix="/harness", tags=["harness"])


@router.get("/state", response_model=HarnessState)
def get_harness_state(token: str = Depends(verify_auth)):
    """Get current harness state (active prompts, tools, strategies)."""
    with get_session() as session:
        prompts = session.query(Prompt).filter(Prompt.status == PromptStatus.active).all()
        tools = session.query(Tool).filter(Tool.status == ToolStatus.active).all()
        strategies = session.query(Strategy).filter(Strategy.status == StrategyStatus.active).all()

        return HarnessState(
            prompts=[
                {"id": p.id, "role": p.role, "version": p.version, "text": p.text}
                for p in prompts
            ],
            tools=[
                {"id": t.id, "name": t.name, "version": t.version, "description": t.description}
                for t in tools
            ],
            strategies=[
                {"id": s.id, "key": s.key, "value": s.value, "version": s.version}
                for s in strategies
            ],
        )


@router.get("/versions", response_model=List[HarnessVersionItem])
def get_harness_versions(token: str = Depends(verify_auth)):
    """Get all harness versions."""
    with get_session() as session:
        versions = session.query(HarnessVersion).order_by(HarnessVersion.id.desc()).all()
        return [
            HarnessVersionItem(
                id=v.id,
                label=v.label,
                ts=v.ts.isoformat(),
                prompt_count=len(v.prompt_set),
                tool_count=len(v.tool_set),
                strategy_count=len(v.strategy_set),
            )
            for v in versions
        ]


@router.get("/versions/{a}/diff/{b}", response_model=VersionDiffResponse)
def diff_versions(a: int, b: int, token: str = Depends(verify_auth)):
    """Get diff between two harness versions."""
    with get_session() as session:
        version_a = session.get(HarnessVersion, a)
        version_b = session.get(HarnessVersion, b)

        if not version_a or not version_b:
            raise HTTPException(status_code=404, detail="Version not found")

        return VersionDiffResponse(
            version_a={
                "id": version_a.id,
                "label": version_a.label,
                "prompts": version_a.prompt_set,
                "tools": version_a.tool_set,
                "strategies": version_a.strategy_set,
            },
            version_b={
                "id": version_b.id,
                "label": version_b.label,
                "prompts": version_b.prompt_set,
                "tools": version_b.tool_set,
                "strategies": version_b.strategy_set,
            },
        )

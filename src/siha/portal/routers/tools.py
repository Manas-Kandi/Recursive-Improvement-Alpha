"""Tool management endpoints."""

from typing import List

from fastapi import APIRouter, Depends

from siha.db import get_session
from siha.models import Tool
from sqlmodel import select
from siha.portal.auth import verify_auth
from siha.schemas import ToolItem

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=List[ToolItem])
def get_tools(token: str = Depends(verify_auth)):
    """Get all tools."""
    with get_session() as session:
        tools = session.exec(select(Tool)).all()
        return [
            ToolItem(
                id=t.id,
                name=t.name,
                version=t.version,
                description=t.description,
                status=t.status,
                implementation_kind=t.implementation_kind,
                source_url=t.source_url,
                created_ts=t.created_ts.isoformat(),
            )
            for t in tools
        ]

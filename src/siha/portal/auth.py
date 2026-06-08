"""Shared auth dependency for portal routers."""

from typing import Optional
from fastapi import Header, HTTPException
from siha.config import settings


def verify_auth(authorization: Optional[str] = Header(None)) -> str:
    """Verify authorization token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.replace("Bearer ", "")
    if token != settings.portal_dev_token:
        raise HTTPException(status_code=403, detail="Invalid token")

    return token

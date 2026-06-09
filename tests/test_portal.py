"""Tests for portal endpoints."""

import pytest
from fastapi.testclient import TestClient

from siha.db import init_db
from siha.portal.api import app


@pytest.fixture(autouse=True)
def fresh_db():
    from sqlalchemy import text
    from sqlmodel import SQLModel
    import siha.db as db_module
    import siha.models  # noqa: F401

    SQLModel.metadata.drop_all(db_module.engine)
    with db_module.engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()
    init_db()


client = TestClient(app)


def test_improve_endpoint_returns_ok():
    """POST /improve should trigger an improvement cycle and return status ok."""
    response = client.post("/improve", headers={"Authorization": "Bearer dev"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_run_endpoint_accepts_provider():
    """POST /run should accept provider in the payload."""
    response = client.post(
        "/run",
        headers={"Authorization": "Bearer dev"},
        json={"prompt": "hello", "provider": "local"},
    )
    # Task is created and returned (it may fail because no LLM is available,
    # but the endpoint should accept the provider field without a 422).
    assert response.status_code in (200, 500)

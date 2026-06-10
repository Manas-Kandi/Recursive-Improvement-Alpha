"""Tests for failure-driven analysis and the template graduated-trust lifecycle."""

import json

import pytest

from siha.db import init_db, get_session
from siha.agent.action_mapper import (
    ActionMapper,
    TemplateSpec,
    record_template_result,
)
from siha.agent.loop import AgentLoop
from siha.harness.scheduler import Scheduler
from siha.models import (
    ActionTemplate, TemplateOrigin, TemplateStatus,
    Task, TaskStatus, TaskCategory,
    Tool, ToolKind, ToolStatus, ToolCall,
)
from sqlmodel import select


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-initialize the database before each test."""
    from sqlalchemy import text
    from sqlmodel import SQLModel
    import siha.db as db_module
    import siha.models  # noqa: F401

    SQLModel.metadata.drop_all(db_module.engine)
    with db_module.engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()
    init_db()


def _seed_template(session, origin=TemplateOrigin.synthesized,
                   success_count=0, failure_count=0,
                   status=TemplateStatus.active, name="synth_test"):
    template = ActionTemplate(
        name=name,
        pattern=r"frobnicate\s+([\w\-./]+)",
        tool_name="write_file",
        args_template={"path": "{1}", "content": ""},
        priority=80,
        origin=origin,
        status=status,
        success_count=success_count,
        failure_count=failure_count,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def _seed_failed_task(session, error_text="No such file or directory: foo.txt"):
    task = Task(
        user_prompt="read foo.txt",
        model="test-model",
        status=TaskStatus.failed,
        category=TaskCategory.user,
        error_summary=None,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    tool = Tool(
        name="read_file", version="1.0.0", description="t",
        implementation_kind=ToolKind.python_code, status=ToolStatus.active,
    )
    session.add(tool)
    session.commit()
    session.refresh(tool)

    call = ToolCall(
        task_id=task.id, tool_id=tool.id,
        args={"path": "foo.txt"},
        result={"error": error_text, "output": ""},
        success=False,
    )
    session.add(call)
    session.commit()
    return task


# ---------- Failure learning ----------

def test_scheduler_analyzes_failed_user_tasks():
    with get_session() as session:
        task = _seed_failed_task(session)
        task_id = task.id

    Scheduler().trigger_improvement()

    with get_session() as session:
        refreshed = session.get(Task, task_id)
        assert refreshed.analyzed is True
        assert refreshed.triage is not None
        assert refreshed.triage.get("failure_categories") == ["missing_path"]


def test_scheduler_skips_failed_benchmark_tasks():
    with get_session() as session:
        task = _seed_failed_task(session)
        task.category = TaskCategory.benchmark
        session.commit()
        task_id = task.id

    Scheduler().trigger_improvement()

    with get_session() as session:
        refreshed = session.get(Task, task_id)
        assert refreshed.analyzed is False


def test_successful_task_records_healthy_triage():
    with get_session() as session:
        task = Task(
            user_prompt="hello", model="test-model",
            status=TaskStatus.success, category=TaskCategory.user,
        )
        session.add(task)
        session.commit()
        task_id = task.id

    Scheduler().trigger_improvement()

    with get_session() as session:
        refreshed = session.get(Task, task_id)
        assert refreshed.analyzed is True
        assert refreshed.triage.get("triage") == "healthy"


# ---------- Graduated trust ----------

def test_synthesized_template_starts_in_probation():
    with get_session() as session:
        _seed_template(session)

    steps = ActionMapper().map("frobnicate widget.txt")
    assert len(steps) == 1
    assert steps[0]["probation"] is True
    assert steps[0]["template_id"] is not None


def test_seed_template_is_never_in_probation():
    with get_session() as session:
        _seed_template(session, origin=TemplateOrigin.seed)

    steps = ActionMapper().map("frobnicate widget.txt")
    assert steps[0]["probation"] is False


def test_template_exits_probation_after_confirmed_successes():
    from siha.config import settings
    with get_session() as session:
        template = _seed_template(
            session, success_count=settings.template_probation_runs,
        )

    steps = ActionMapper().map("frobnicate widget.txt")
    assert steps[0]["probation"] is False


def test_record_result_increments_counters():
    with get_session() as session:
        template = _seed_template(session)
        tid = template.id

    record_template_result(tid, success=True)
    record_template_result(tid, success=False)

    with get_session() as session:
        refreshed = session.get(ActionTemplate, tid)
        assert refreshed.success_count == 1
        assert refreshed.failure_count == 1
        assert refreshed.status == TemplateStatus.active


def test_repeated_failures_archive_synthesized_template():
    from siha.config import settings
    with get_session() as session:
        template = _seed_template(
            session, failure_count=settings.template_failure_archive_threshold - 1,
        )
        tid = template.id

    archived = record_template_result(tid, success=False)
    assert archived is True

    with get_session() as session:
        refreshed = session.get(ActionTemplate, tid)
        assert refreshed.status == TemplateStatus.archived

    # An archived template no longer matches.
    assert ActionMapper().map("frobnicate widget.txt") == []


def test_seed_templates_are_never_auto_archived():
    from siha.config import settings
    with get_session() as session:
        template = _seed_template(
            session, origin=TemplateOrigin.seed,
            failure_count=settings.template_failure_archive_threshold + 5,
        )
        tid = template.id

    archived = record_template_result(tid, success=False)
    assert archived is False

    with get_session() as session:
        assert session.get(ActionTemplate, tid).status == TemplateStatus.active


def test_successes_protect_template_from_archive():
    """A template with more successes than failures is not archived."""
    from siha.config import settings
    with get_session() as session:
        template = _seed_template(
            session,
            success_count=settings.template_failure_archive_threshold + 2,
            failure_count=settings.template_failure_archive_threshold - 1,
        )
        tid = template.id

    archived = record_template_result(tid, success=False)
    assert archived is False


# ---------- Shadow agreement ----------

def _step(tool, **args):
    return {
        "id": "x", "type": "function",
        "function": {"name": tool, "arguments": json.dumps(args)},
    }


def test_steps_agree_same_tool_and_path():
    a = _step("write_file", path="notes.md", content="")
    b = _step("write_file", path="./notes.md", content="# Notes\n")
    assert AgentLoop._steps_agree(a, b) is True


def test_steps_disagree_on_tool():
    a = _step("write_file", path="notes.md")
    b = _step("run_shell", command="touch notes.md")
    assert AgentLoop._steps_agree(a, b) is False


def test_steps_disagree_on_path():
    a = _step("write_file", path="notes.md")
    b = _step("write_file", path="todo.md")
    assert AgentLoop._steps_agree(a, b) is False


def test_steps_agree_on_command_head():
    a = _step("run_shell", command="mkdir -p demo")
    b = _step("run_shell", command="mkdir demo")
    assert AgentLoop._steps_agree(a, b) is True


def test_steps_disagree_on_command_head():
    a = _step("run_shell", command="rm -rf demo")
    b = _step("run_shell", command="mkdir demo")
    assert AgentLoop._steps_agree(a, b) is False

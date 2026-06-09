"""Tests for mutation candidate lifecycle, version isolation, and rollback."""

import pytest
from siha.db import init_db, get_session
from siha.models import (
    Prompt, PromptRole, PromptStatus,
    Tool, ToolKind, ToolStatus,
    Strategy, StrategyStatus,
    Mutation, MutationStatus, MutationKind,
    HarnessVersion,
)
from siha.harness.mutator import Mutator
from siha.harness.evaluator import Evaluator
from siha.tools.registry import ToolRegistry
from siha.agent.prompts import get_active_prompt
from sqlmodel import select


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-initialize the database before each test."""
    from sqlalchemy import text
    from sqlmodel import SQLModel
    import siha.db as db_module
    import siha.models  # noqa: F401 – ensure metadata is populated
    # Drop all tables (including Alembic version tracking) and recreate schema
    SQLModel.metadata.drop_all(db_module.engine)
    with db_module.engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()
    init_db()


def _seed_prompt(session, text="default", role=PromptRole.system, status=PromptStatus.active):
    prompt = Prompt(role=role, version="1.0.0", text=text, status=status)
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return prompt


def _seed_tool(session, name="test_tool", status=ToolStatus.active):
    tool = Tool(
        name=name,
        version="1.0.0",
        description="A test tool",
        json_schema={},
        implementation_kind=ToolKind.python_code,
        code="def run(**kwargs): return 42",
        status=status,
    )
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return tool


def _seed_strategy(session, key="test_strategy", status=StrategyStatus.active):
    strategy = Strategy(key=key, value={"foo": "bar"}, version="1.0.0", status=status)
    session.add(strategy)
    session.commit()
    session.refresh(strategy)
    return strategy


class TestPromptMutationLifecycle:
    def test_propose_prompt_mutation(self):
        with get_session() as session:
            old = _seed_prompt(session, text="old system prompt")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "prompt",
            "target": "system",
            "before": "old system prompt",
            "after": {"text": "new system prompt"},
            "rationale": "Better instructions",
        })

        assert mutation.status == MutationStatus.proposed
        assert mutation.kind == MutationKind.prompt

    def test_apply_prompt_creates_candidate(self):
        with get_session() as session:
            old = _seed_prompt(session, text="old system prompt")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "prompt",
            "target": "system",
            "before": "old system prompt",
            "after": {"text": "new system prompt"},
            "rationale": "Better instructions",
        })
        version = mutator.apply_mutation(mutation)

        with get_session() as session:
            prompts = session.exec(select(Prompt)).all()
            assert len(prompts) == 2

            old_refreshed = session.get(Prompt, old.id)
            assert old_refreshed.status == PromptStatus.active

            candidate = session.exec(select(Prompt).where(
                Prompt.status == PromptStatus.candidate
            )).first()
            assert candidate is not None
            assert candidate.text == "new system prompt"

            mutation = session.get(Mutation, mutation.id)
            assert mutation.status == MutationStatus.candidate
            assert mutation.base_version_id is not None
            assert mutation.candidate_version_id == version.id

    def test_promote_prompt_archives_old(self):
        with get_session() as session:
            old = _seed_prompt(session, text="old system prompt")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "prompt",
            "target": "system",
            "after": {"text": "new system prompt"},
            "rationale": "Better instructions",
        })
        mutator.apply_mutation(mutation)
        mutator.promote_mutation(mutation)

        with get_session() as session:
            old_refreshed = session.get(Prompt, old.id)
            assert old_refreshed.status == PromptStatus.archived

            candidate = session.exec(select(Prompt).where(
                Prompt.status == PromptStatus.active
            )).first()
            assert candidate.text == "new system prompt"

            mutation = session.get(Mutation, mutation.id)
            assert mutation.status == MutationStatus.promoted

    def test_rollback_prompt_restores_old(self):
        with get_session() as session:
            old = _seed_prompt(session, text="old system prompt")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "prompt",
            "target": "system",
            "after": {"text": "new system prompt"},
            "rationale": "Better instructions",
        })
        mutator.apply_mutation(mutation)
        mutator.rollback_mutation(mutation)

        with get_session() as session:
            old_refreshed = session.get(Prompt, old.id)
            assert old_refreshed.status == PromptStatus.active

            candidate = session.exec(select(Prompt).where(
                Prompt.status == PromptStatus.candidate
            )).first()
            assert candidate is None

            mutation = session.get(Mutation, mutation.id)
            assert mutation.status == MutationStatus.rolled_back


class TestToolMutationLifecycle:
    def test_apply_tool_creates_candidate(self):
        with get_session() as session:
            old = _seed_tool(session, name="adder")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "tool",
            "target": "adder",
            "after": {"name": "adder", "code": "def run(**kwargs): return kwargs.get('a',0)+kwargs.get('b',0)"},
            "rationale": "Support multiple args",
        })
        version = mutator.apply_mutation(mutation)

        with get_session() as session:
            old_refreshed = session.get(Tool, old.id)
            assert old_refreshed.status == ToolStatus.active

            candidate = session.exec(select(Tool).where(
                Tool.status == ToolStatus.candidate
            )).first()
            assert candidate is not None
            assert candidate.name == "adder"

            mutation = session.get(Mutation, mutation.id)
            assert mutation.status == MutationStatus.candidate

    def test_promote_tool_deprecates_old(self):
        with get_session() as session:
            old = _seed_tool(session, name="adder")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "tool",
            "target": "adder",
            "after": {"name": "adder", "code": "def run(**kwargs): return kwargs.get('a',0)+kwargs.get('b',0)"},
            "rationale": "Support multiple args",
        })
        mutator.apply_mutation(mutation)
        mutator.promote_mutation(mutation)

        with get_session() as session:
            old_refreshed = session.get(Tool, old.id)
            assert old_refreshed.status == ToolStatus.archived

            active = session.exec(select(Tool).where(
                Tool.status == ToolStatus.active
            )).first()
            assert active.code == "def run(**kwargs): return kwargs.get('a',0)+kwargs.get('b',0)"

    def test_rollback_tool_keeps_old_active(self):
        with get_session() as session:
            old = _seed_tool(session, name="adder")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "tool",
            "target": "adder",
            "after": {"name": "adder", "code": "new code"},
            "rationale": "Change",
        })
        mutator.apply_mutation(mutation)
        mutator.rollback_mutation(mutation)

        with get_session() as session:
            old_refreshed = session.get(Tool, old.id)
            assert old_refreshed.status == ToolStatus.active

            candidate = session.exec(select(Tool).where(
                Tool.status == ToolStatus.candidate
            )).first()
            assert candidate is None


class TestVersionIsolation:
    def test_tool_registry_loads_version_specific_tools(self):
        with get_session() as session:
            tool_a = _seed_tool(session, name="tool_a")
            tool_b = _seed_tool(session, name="tool_b")
            tool_a_id = tool_a.id
            tool_b_id = tool_b.id

        with get_session() as session:
            version = HarnessVersion(
                label="test_v1",
                prompt_set=[],
                tool_set=[tool_a_id],
                strategy_set=[],
            )
            session.add(version)
            session.commit()
            session.refresh(version)
            version_id = version.id

        registry = ToolRegistry(harness_version_id=version_id)
        names = registry.list_tools()
        assert "tool_a" in names
        assert "tool_b" not in names

    def test_prompt_lookup_uses_version(self):
        with get_session() as session:
            active_prompt = _seed_prompt(session, text="active prompt", status=PromptStatus.active)
            candidate_prompt = _seed_prompt(session, text="candidate prompt", status=PromptStatus.candidate)

        # Without version, returns active prompt
        assert get_active_prompt(PromptRole.system) == "active prompt"

        with get_session() as session:
            version = HarnessVersion(
                label="test_v1",
                prompt_set=[candidate_prompt.id],
                tool_set=[],
                strategy_set=[],
            )
            session.add(version)
            session.commit()
            session.refresh(version)
            version_id = version.id

        # With version, returns candidate prompt
        assert get_active_prompt(PromptRole.system, harness_version_id=version_id) == "candidate prompt"


class TestEvaluatorStates:
    def test_should_promote_requires_candidate_state(self):
        with get_session() as session:
            old = _seed_prompt(session, text="old")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "prompt",
            "target": "system",
            "after": {"text": "new"},
            "rationale": "Change",
        })
        # Not yet applied
        evaluator = Evaluator()
        assert evaluator.should_promote(mutation) is False

        mutator.apply_mutation(mutation)
        # After apply, it has base and candidate versions
        # Since there are no benchmarks, evaluate_version returns 0.0 for both,
        # so delta is 0, which is not >= threshold (default 0.05).
        assert evaluator.should_promote(mutation) is False

    def test_should_promote_first_version_no_benchmarks(self):
        with get_session() as session:
            old = _seed_prompt(session, text="old")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "prompt",
            "target": "system",
            "after": {"text": "new"},
            "rationale": "Change",
        })
        mutator.apply_mutation(mutation)

        evaluator = Evaluator()
        # With no benchmarks, scores are 0.0 vs 0.0, delta = 0
        # Not an improvement, so should_promote returns False
        assert evaluator.should_promote(mutation) is False

        with get_session() as session:
            refreshed = session.get(Mutation, mutation.id)
            assert refreshed.status == MutationStatus.evaluating
            assert refreshed.benchmark_delta == 0.0


class TestMutationVersionTracking:
    def test_apply_creates_base_and_candidate_versions(self):
        with get_session() as session:
            old = _seed_prompt(session, text="old")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "prompt",
            "target": "system",
            "after": {"text": "new"},
            "rationale": "Change",
        })
        version = mutator.apply_mutation(mutation)

        with get_session() as session:
            mutation = session.get(Mutation, mutation.id)
            assert mutation.base_version_id is not None
            assert mutation.candidate_version_id is not None
            assert mutation.candidate_version_id == version.id

            base_version = session.get(HarnessVersion, mutation.base_version_id)
            candidate_version = session.get(HarnessVersion, mutation.candidate_version_id)
            assert base_version.id != candidate_version.id
            # Base version should contain the old active prompt
            assert len(base_version.prompt_set) == 1
            assert old.id in base_version.prompt_set
            # Candidate version should replace old with candidate
            assert len(candidate_version.prompt_set) == 1
            assert old.id not in candidate_version.prompt_set

    def test_rollback_creates_new_version(self):
        with get_session() as session:
            _seed_prompt(session, text="old")

        mutator = Mutator()
        mutation = mutator.propose_mutation({
            "kind": "prompt",
            "target": "system",
            "after": {"text": "new"},
            "rationale": "Change",
        })
        mutator.apply_mutation(mutation)
        version = mutator.rollback_mutation(mutation)

        with get_session() as session:
            mutation = session.get(Mutation, mutation.id)
            assert mutation.status == MutationStatus.rolled_back
            # Rollback should create a new version snapshot
            assert version.id is not None

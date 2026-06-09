"""Tests for the DB-backed action template layer and template synthesis."""

import json
import re

import pytest

from siha.agent.action_mapper import (
    ActionMapper,
    DEFAULT_TEMPLATES,
    render_args,
    seed_default_templates,
)
from siha.db import init_db, get_session
from siha.harness.mutator import Mutator
from siha.harness.synthesizer import TemplateSynthesizer
from siha.models import (
    ActionTemplate,
    HarnessVersion,
    Mutation,
    MutationKind,
    MutationStatus,
    TemplateOrigin,
    TemplateStatus,
)
from sqlmodel import select


# ---------- Matching behaviour ----------

def _calls(steps):
    return [
        (s["function"]["name"], json.loads(s["function"]["arguments"]))
        for s in steps
    ]


def test_create_folder_maps_to_mkdir():
    mapper = ActionMapper()
    steps = mapper.map("create a folder called demo")
    calls = _calls(steps)
    assert ("run_shell", {"command": "mkdir -p demo"}) in calls


def test_file_with_content_yields_exactly_one_write():
    """Overlapping write templates must not fire twice on the same span."""
    mapper = ActionMapper()
    steps = mapper.map("create a file called notes.txt with hello world")
    write_calls = [c for c in _calls(steps) if c[0] == "write_file"]
    assert len(write_calls) == 1
    assert write_calls[0][1]["content"] == "hello world"


def test_compound_request_orders_by_position():
    mapper = ActionMapper()
    steps = mapper.map("make a folder named app and then list .")
    calls = _calls(steps)
    assert calls[0] == ("run_shell", {"command": "mkdir -p app"})


def test_novel_request_returns_empty():
    mapper = ActionMapper()
    assert mapper.map("philosophize about the meaning of computation") == []


def test_render_args_substitutes_groups():
    match = re.search(r"(\w+) to (\w+)", "alpha to beta")
    args = render_args({"command": "mv {1} {2}", "note": "static"}, match)
    assert args == {"command": "mv alpha beta", "note": "static"}


def test_render_args_missing_group_is_empty():
    match = re.search(r"(\w+)", "solo")
    args = render_args({"x": "{1}-{9}"}, match)
    assert args == {"x": "solo-"}


# ---------- DB-backed loading ----------

def test_seed_and_load_templates_from_db():
    init_db()
    seed_default_templates()
    with get_session() as session:
        rows = session.exec(select(ActionTemplate).where(
            ActionTemplate.status == TemplateStatus.active,
        )).all()
    assert len(rows) >= len(DEFAULT_TEMPLATES)

    mapper = ActionMapper()
    assert mapper.template_count >= len(DEFAULT_TEMPLATES)
    steps = mapper.map("create a folder called dbtest")
    assert _calls(steps)[0] == ("run_shell", {"command": "mkdir -p dbtest"})


def test_version_pinned_template_loading():
    init_db()
    seed_default_templates()
    with get_session() as session:
        row = session.exec(select(ActionTemplate).where(
            ActionTemplate.name == "create_folder",
        )).first()
        version = HarnessVersion(label="pin-test", template_set=[row.id])
        session.add(version)
        session.commit()
        session.refresh(version)
        version_id = version.id

    mapper = ActionMapper(harness_version_id=version_id)
    assert mapper.template_count == 1


# ---------- Mutation lifecycle ----------

def test_template_mutation_lifecycle():
    init_db()
    mutator = Mutator()

    mutation = mutator.propose_mutation({
        "kind": MutationKind.template,
        "target": "test_lifecycle_template",
        "before": {},
        "after": {
            "name": "test_lifecycle_template",
            "pattern": r"frobnicate\s+([\w\-./]+)",
            "tool_name": "run_shell",
            "args_template": {"command": "echo {1}"},
            "priority": 75,
            "origin": TemplateOrigin.synthesized,
        },
        "rationale": "test",
    })
    assert mutation.status == MutationStatus.proposed

    candidate_version = mutator.apply_mutation(mutation)
    assert candidate_version.id is not None

    with get_session() as session:
        mutation = session.get(Mutation, mutation.id)
        assert mutation.status == MutationStatus.candidate
        candidate = session.get(ActionTemplate, mutation.target_id)
        assert candidate.status == TemplateStatus.candidate
        # Candidate version must include the candidate template.
        version = session.get(HarnessVersion, candidate_version.id)
        assert candidate.id in version.template_set

    # Candidate version should be matchable when pinned.
    pinned = ActionMapper(harness_version_id=candidate_version.id)
    steps = pinned.map("frobnicate gadget")
    assert ("run_shell", {"command": "echo gadget"}) in _calls(steps)

    # Unpinned mapper must NOT see the candidate.
    unpinned = ActionMapper()
    assert unpinned.map("frobnicate gadget") == []

    mutator.promote_mutation(mutation)
    with get_session() as session:
        candidate = session.get(ActionTemplate, mutation.target_id)
        assert candidate.status == TemplateStatus.active

    # Now globally visible.
    steps = ActionMapper().map("frobnicate gadget")
    assert ("run_shell", {"command": "echo gadget"}) in _calls(steps)

    # Cleanup: archive so other tests aren't affected.
    with get_session() as session:
        candidate = session.get(ActionTemplate, mutation.target_id)
        candidate.status = TemplateStatus.archived
        session.commit()


def test_template_mutation_rollback():
    init_db()
    mutator = Mutator()
    mutation = mutator.propose_mutation({
        "kind": MutationKind.template,
        "target": "test_rollback_template",
        "after": {
            "name": "test_rollback_template",
            "pattern": r"zorble\s+(\w+)",
            "tool_name": "run_shell",
            "args_template": {"command": "echo {1}"},
        },
        "rationale": "test",
    })
    mutator.apply_mutation(mutation)
    mutator.rollback_mutation(mutation)

    with get_session() as session:
        mutation = session.get(Mutation, mutation.id)
        assert mutation.status == MutationStatus.rolled_back
        candidate = session.get(ActionTemplate, mutation.target_id)
        assert candidate.status == TemplateStatus.archived

    assert ActionMapper().map("zorble thing") == []


# ---------- Synthesis (generalization) ----------

def test_generalize_extracts_capture_groups():
    result = TemplateSynthesizer.generalize(
        "deploy the service called billing-api",
        "run_shell",
        {"command": "deploy billing-api"},
    )
    assert result is not None
    pattern, args_template = result
    match = re.search(pattern, "deploy the service called auth-api", re.IGNORECASE)
    assert match is not None
    rendered = render_args(args_template, match)
    assert rendered["command"] == "deploy auth-api"


def test_generalize_returns_none_when_args_not_in_prompt():
    result = TemplateSynthesizer.generalize(
        "do something opaque",
        "run_shell",
        {"command": "ls -la /var/log"},
    )
    assert result is None


def test_generalize_handles_multiple_args():
    result = TemplateSynthesizer.generalize(
        "backup data.db to archive/",
        "run_shell",
        {"command": "cp data.db archive/"},
    )
    assert result is not None
    pattern, args_template = result
    match = re.search(pattern, "backup users.db to vault/", re.IGNORECASE)
    assert match is not None
    rendered = render_args(args_template, match)
    assert rendered["command"] == "cp users.db vault/"

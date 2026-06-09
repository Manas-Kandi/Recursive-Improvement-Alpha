"""Tests for filesystem-grounded benchmark scoring and evaluator rigor."""

from pathlib import Path

import pytest

from siha.benchmarks.runner import BenchmarkRunner
from siha.benchmarks.generator import BenchmarkGenerator
from siha.db import init_db, get_session
from siha.harness.evaluator import Evaluator
from siha.harness.synthesizer import TemplateSynthesizer
from siha.models import (
    Benchmark,
    BenchmarkOrigin,
    BenchmarkRun,
    HarnessVersion,
    Task,
    TaskStatus,
)
from sqlmodel import select


def _make_benchmark(session, name, assertion):
    bench = session.exec(select(Benchmark).where(Benchmark.name == name)).first()
    if bench is None:
        bench = Benchmark(
            name=name,
            category="test",
            task_spec={"prompt": "x"},
            assertion=assertion,
            origin=BenchmarkOrigin.seed,
        )
    else:
        bench.assertion = assertion
    session.add(bench)
    session.commit()
    session.refresh(bench)
    return bench


def _make_task(session, status=TaskStatus.success):
    task = Task(user_prompt="x", model="m", status=status)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


# ---------- Filesystem-grounded file checks ----------

def test_file_check_passes_when_file_exists(tmp_path):
    init_db()
    (tmp_path / "result.txt").write_text("Hello World")
    with get_session() as session:
        bench = _make_benchmark(session, "fs_check_pass", {
            "file_checks": [{"path": "result.txt", "content_regex": "Hello"}],
        })
        task = _make_task(session)

    score = BenchmarkRunner()._score_assertions(bench, task, workspace=tmp_path)
    assert score == 1.0


def test_file_check_fails_when_file_missing(tmp_path):
    init_db()
    with get_session() as session:
        bench = _make_benchmark(session, "fs_check_missing", {
            "file_checks": [{"path": "ghost.txt"}],
        })
        task = _make_task(session)

    score = BenchmarkRunner()._score_assertions(bench, task, workspace=tmp_path)
    assert score == 0.0


def test_file_check_fails_on_wrong_content(tmp_path):
    init_db()
    (tmp_path / "result.txt").write_text("something else")
    with get_session() as session:
        bench = _make_benchmark(session, "fs_check_content", {
            "file_checks": [{"path": "result.txt", "content_regex": "Hello World"}],
        })
        task = _make_task(session)

    score = BenchmarkRunner()._score_assertions(bench, task, workspace=tmp_path)
    assert score == 0.0


def test_talking_about_file_does_not_pass(tmp_path):
    """An agent that only LOGS the filename (no file on disk) must score 0."""
    init_db()
    with get_session() as session:
        bench = _make_benchmark(session, "fs_check_talk", {
            "file_checks": [{"path": "test.txt"}],
        })
        task = _make_task(session)
        task.final_answer = "I created test.txt for you!"
        session.commit()

    score = BenchmarkRunner()._score_assertions(bench, task, workspace=tmp_path)
    assert score == 0.0


# ---------- Evaluator caching / repetition ----------

def test_evaluator_uses_cached_runs(monkeypatch):
    init_db()
    from siha.config import settings

    with get_session() as session:
        version = HarnessVersion(label="cache-test")
        session.add(version)
        bench = _make_benchmark(session, "cache_bench", {"exit_code": 0})
        session.commit()
        session.refresh(version)
        version_id = version.id
        bench_id = bench.id

        # Pre-record a full set of cached runs.
        for _ in range(settings.benchmark_runs):
            session.add(BenchmarkRun(
                benchmark_id=bench_id,
                harness_version=version_id,
                passed=True,
                score=1.0,
                duration_ms=1,
                output={},
            ))
        session.commit()

    evaluator = Evaluator()

    def _explode(*args, **kwargs):
        raise AssertionError("runner must not execute when cache is complete")

    monkeypatch.setattr(evaluator.runner, "run_benchmark", _explode)
    scores = evaluator._benchmark_scores(
        _get_bench(bench_id), version_id,
    )
    assert scores == [1.0] * settings.benchmark_runs


def _get_bench(bench_id):
    with get_session() as session:
        return session.get(Benchmark, bench_id)


# ---------- Generator dedupe / cap ----------

def test_generator_dedupes_identical_prompts():
    init_db()
    with get_session() as session:
        existing = session.exec(select(Benchmark).where(
            Benchmark.name == "dedupe_target",
        )).first()
        bench = existing or _make_benchmark(session, "dedupe_target", {"exit_code": 0})
        bench.task_spec = {"prompt": "make a widget named foo"}
        session.add(bench)
        session.commit()

    gen = BenchmarkGenerator.__new__(BenchmarkGenerator)  # skip LLM client init
    assert gen._is_duplicate_prompt("make a widget named foo") is True
    assert gen._is_duplicate_prompt("Make a   widget named FOO") is True
    assert gen._is_duplicate_prompt("calculate fibonacci sequence please") is False


# ---------- Regression benchmark synthesis ----------

def test_regression_benchmark_created_for_write_file():
    init_db()
    bench = TemplateSynthesizer._create_regression_benchmark(
        999991,
        "create greeting.txt with hi there",
        "write_file",
        {"path": "greeting.txt", "content": "hi there"},
    )
    assert bench is not None
    assert bench.category == "regression"
    assert bench.assertion["file_checks"][0]["path"] == "greeting.txt"
    assert "hi\\ there" in bench.assertion["file_checks"][0]["content_regex"] or \
        "hi there" in bench.assertion["file_checks"][0]["content_regex"]


def test_regression_benchmark_for_mkdir_checks_dir():
    init_db()
    bench = TemplateSynthesizer._create_regression_benchmark(
        999992,
        "create a folder called stuff",
        "run_shell",
        {"command": "mkdir -p stuff"},
    )
    assert bench is not None
    assert bench.assertion["file_checks"][0]["path"] == "stuff"

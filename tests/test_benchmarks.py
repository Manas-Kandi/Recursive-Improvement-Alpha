"""Tests for benchmark assertion scoring."""

from siha.benchmarks.runner import BenchmarkRunner
from siha.db import init_db, get_session
from siha.models import Benchmark, BenchmarkOrigin, Task, TaskStatus, Step, StepType


def test_benchmark_scores_stdout_regex_from_trace():
    init_db()
    with get_session() as session:
        task = Task(user_prompt="x", model="m", status=TaskStatus.success, final_answer="answer")
        session.add(task)
        session.commit()
        session.refresh(task)
        step = Step(
            task_id=task.id,
            idx=0,
            type=StepType.observation,
            content={"output": "the result is 55"},
        )
        benchmark = Benchmark(
            name=f"bench_score_{task.id}",
            category="math",
            task_spec={"prompt": "x"},
            assertion={"exit_code": 0, "stdout_regex": r"\b55\b"},
            origin=BenchmarkOrigin.seed,
        )
        session.add(step)
        session.add(benchmark)
        session.commit()
        session.refresh(benchmark)
        task_id = task.id
        benchmark_id = benchmark.id

    with get_session() as session:
        task = session.get(Task, task_id)
        benchmark = session.get(Benchmark, benchmark_id)
        score = BenchmarkRunner()._score_assertions(benchmark, task)

    assert score == 1.0

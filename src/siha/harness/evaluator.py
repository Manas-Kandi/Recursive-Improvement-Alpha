"""Run benchmarks, score, and compare harness versions"""

from typing import Dict, Any, List, Optional
from siha.db import get_session
from siha.models import Benchmark, BenchmarkRun, HarnessVersion, Mutation, MutationKind, MutationStatus
from sqlmodel import select
from siha.benchmarks.runner import BenchmarkRunner
from siha.config import settings


class Evaluator:
    """Evaluates harness versions against benchmark suite.

    Each benchmark is executed ``settings.benchmark_runs`` times and the
    scores are averaged, so one flaky run cannot flip a promotion decision.
    Previously recorded scores for a version are reused when caching is on,
    which avoids re-running the (expensive) base version suite on every
    candidate comparison.
    """

    def __init__(self):
        self.runner = BenchmarkRunner()

    def evaluate_version(self, version_id: int, force: bool = False) -> float:
        """Score a harness version: mean over all benchmarks x repetitions."""
        with get_session() as session:
            version = session.get(HarnessVersion, version_id)
            if not version:
                return 0.0

            benchmarks = session.exec(select(Benchmark)).all()

        if not benchmarks:
            return 0.0

        per_benchmark_means: List[float] = []
        for benchmark in benchmarks:
            scores = self._benchmark_scores(benchmark, version_id, force=force)
            per_benchmark_means.append(sum(scores) / len(scores))

        return sum(per_benchmark_means) / len(per_benchmark_means)

    def _benchmark_scores(
        self,
        benchmark: Benchmark,
        version_id: int,
        force: bool = False,
    ) -> List[float]:
        """Get ``benchmark_runs`` scores for a benchmark/version pair.

        Reuses cached BenchmarkRun rows when available; otherwise executes the
        missing repetitions and records them.
        """
        n_runs = max(1, settings.benchmark_runs)
        cached: List[float] = []

        if settings.benchmark_cache and not force:
            with get_session() as session:
                rows = session.exec(select(BenchmarkRun).where(
                    BenchmarkRun.benchmark_id == benchmark.id,
                    BenchmarkRun.harness_version == version_id,
                ).order_by(BenchmarkRun.id.desc()).limit(n_runs)).all()
                cached = [r.score for r in rows]

        missing = n_runs - len(cached)
        for _ in range(missing):
            run = self.runner.run_benchmark(benchmark, version_id)
            cached.append(run.score)

        return cached[:n_runs]

    def compare_versions(self, version_a_id: int, version_b_id: int) -> Dict[str, Any]:
        """Compare two harness versions and return delta"""
        score_a = self.evaluate_version(version_a_id)
        score_b = self.evaluate_version(version_b_id)

        delta = score_b - score_a

        return {
            "version_a": version_a_id,
            "version_b": version_b_id,
            "score_a": score_a,
            "score_b": score_b,
            "delta": delta,
            "improvement": delta >= settings.benchmark_promote_threshold,
        }

    def should_promote(self, mutation: Mutation) -> bool:
        """Determine if a mutation should be promoted based on benchmark results.

        Uses the mutation's ``base_version_id`` and ``candidate_version_id`` to
        run an isolated comparison. Returns True if the candidate improves over
        the base by at least ``benchmark_promote_threshold``.
        """
        with get_session() as session:
            mutation = session.get(Mutation, mutation.id)
            if not mutation:
                return False

            # Mutations must be in candidate state before evaluation
            if mutation.status not in (MutationStatus.candidate, MutationStatus.evaluating):
                return False

            base_version_id = mutation.base_version_id
            candidate_version_id = mutation.candidate_version_id

            if not base_version_id or not candidate_version_id:
                return False

            mutation.status = MutationStatus.evaluating
            session.commit()

        comparison = self.compare_versions(base_version_id, candidate_version_id)

        with get_session() as session:
            mutation = session.get(Mutation, mutation.id)
            mutation.benchmark_delta = comparison["delta"]
            session.commit()

        if comparison["improvement"]:
            return True

        if comparison["delta"] < -settings.benchmark_promote_threshold:
            return False

        # Template mutations ADD capability the historical suite doesn't
        # measure (their own regression benchmark is part of the candidate
        # evaluation). Promote on non-regression instead of strict improvement.
        with get_session() as session:
            mutation = session.get(Mutation, mutation.id)
            if mutation and mutation.kind == MutationKind.template:
                return comparison["delta"] >= 0

        return False

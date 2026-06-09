"""Run benchmarks, score, and compare harness versions"""

from typing import Dict, Any, Optional
from siha.db import get_session
from siha.models import Benchmark, HarnessVersion, Mutation, MutationStatus
from sqlmodel import select
from siha.benchmarks.runner import BenchmarkRunner
from siha.config import settings


class Evaluator:
    """Evaluates harness versions against benchmark suite"""

    def __init__(self):
        self.runner = BenchmarkRunner()

    def evaluate_version(self, version_id: int) -> float:
        """Run all benchmarks against a harness version and return aggregate score"""
        with get_session() as session:
            version = session.get(HarnessVersion, version_id)
            if not version:
                return 0.0

            benchmarks = session.exec(select(Benchmark)).all()

        total_score = 0.0
        for benchmark in benchmarks:
            run = self.runner.run_benchmark(benchmark, version_id)
            total_score += run.score

        return total_score / len(benchmarks) if benchmarks else 0.0

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

        return False

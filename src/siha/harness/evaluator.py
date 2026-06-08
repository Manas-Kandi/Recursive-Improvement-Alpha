"""Run benchmarks, score, and compare harness versions"""

from typing import List, Dict, Any, Optional
from siha.db import get_session
from siha.models import Benchmark, BenchmarkRun, HarnessVersion, Mutation, MutationStatus
from siha.benchmarks.runner import BenchmarkRunner
from siha.config import settings
from datetime import datetime


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
            
            benchmarks = session.query(Benchmark).all()
        
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
            "improvement": delta >= settings.benchmark_promote_threshold
        }
    
    def should_promote(self, mutation: Mutation) -> bool:
        """Determine if a mutation should be promoted based on benchmark results"""
        
        with get_session() as session:
            # Get the version before and after mutation
            # This is simplified - in production would track version lineage
            current_version = session.query(HarnessVersion).order_by(
                HarnessVersion.id.desc()
            ).first()
            
            if not current_version:
                return False
            
            # Get previous version
            previous_version = session.query(HarnessVersion).filter(
                HarnessVersion.id < current_version.id
            ).order_by(HarnessVersion.id.desc()).first()
            
            if not previous_version:
                return True  # First version, promote by default
            
            # Compare
            comparison = self.compare_versions(previous_version.id, current_version.id)
            
            # Update mutation with benchmark delta
            mutation.benchmark_delta = comparison["delta"]
            session.commit()
            
            # Check threshold
            if comparison["improvement"]:
                return True
            
            # If regression, mark for rollback
            if comparison["delta"] < -settings.benchmark_promote_threshold:
                mutation.status = MutationStatus.reverted
                session.commit()
                return False
            
            return False

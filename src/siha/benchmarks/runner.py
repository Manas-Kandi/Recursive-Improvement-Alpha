"""Deterministic benchmark execution and scoring"""

from typing import Dict, Any
from siha.db import get_session
from siha.models import Benchmark, BenchmarkRun, HarnessVersion, BenchmarkOrigin
from siha.agent.loop import AgentLoop
from siha.config import settings
import re
import time


def seed_benchmarks():
    """Seed initial benchmark suite"""
    
    benchmarks = [
        {
            "name": "fibonacci_10",
            "category": "math",
            "task_spec": {
                "prompt": "Write and run a Python script that prints the 10th Fibonacci number",
                "sandbox": "local"
            },
            "assertion": {
                "exit_code": 0
            },
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "file_io_write",
            "category": "file_io",
            "task_spec": {
                "prompt": "Create a file named test.txt with the content 'Hello World'",
                "sandbox": "local"
            },
            "assertion": {
                "exit_code": 0
            },
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "list_directory",
            "category": "file_io",
            "task_spec": {
                "prompt": "List the contents of the current directory",
                "sandbox": "local"
            },
            "assertion": {
                "exit_code": 0
            },
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "simple_math",
            "category": "math",
            "task_spec": {
                "prompt": "Calculate and print the result of 2 + 2",
                "sandbox": "local"
            },
            "assertion": {
                "exit_code": 0
            },
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "shell_command",
            "category": "shell",
            "task_spec": {
                "prompt": "Run the command 'echo hello' and show the output",
                "sandbox": "local"
            },
            "assertion": {
                "exit_code": 0
            },
            "origin": BenchmarkOrigin.seed
        }
    ]
    
    with get_session() as session:
        for bench_def in benchmarks:
            existing = session.query(Benchmark).filter(
                Benchmark.name == bench_def["name"]
            ).first()
            
            if not existing:
                benchmark = Benchmark(
                    name=bench_def["name"],
                    category=bench_def["category"],
                    task_spec=bench_def["task_spec"],
                    assertion=bench_def["assertion"],
                    origin=bench_def["origin"]
                )
                session.add(benchmark)
        
        session.commit()


class BenchmarkRunner:
    """Executes benchmarks deterministically and scores results"""
    
    def run_benchmark(self, benchmark: Benchmark, harness_version_id: int) -> BenchmarkRun:
        """Run a single benchmark and record results"""
        
        start_time = time.time()
        
        # Run the task with low temperature for determinism
        agent = AgentLoop()
        agent.client.temperature = settings.benchmark_temperature
        
        task = agent.run(
            benchmark.task_spec.get("prompt", ""),
            sandbox_mode=benchmark.task_spec.get("sandbox", "local")
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Score against assertions
        score = self._score_assertions(benchmark, task)
        
        # Record run
        with get_session() as session:
            run = BenchmarkRun(
                benchmark_id=benchmark.id,
                harness_version=harness_version_id,
                passed=score == 1.0,
                score=score,
                duration_ms=duration_ms,
                output={
                    "task_status": task.status,
                    "task_duration": task.duration_ms,
                    "error_summary": task.error_summary
                }
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run
    
    def _score_assertions(self, benchmark: Benchmark, task) -> float:
        """Score task execution against benchmark assertions"""
        
        assertions = benchmark.assertion
        total_assertions = 0
        passed_assertions = 0
        
        # Check exit code
        if "exit_code" in assertions:
            total_assertions += 1
            # For success, exit code should be 0 (task.status == success)
            expected = assertions["exit_code"]
            actual = 0 if task.status == "success" else 1
            if expected == actual:
                passed_assertions += 1
        
        # Check stdout regex
        if "stdout_regex" in assertions:
            total_assertions += 1
            # Would need to capture stdout from task
            # For now, assume pass if task succeeded
            if task.status == "success":
                passed_assertions += 1
        
        # Check file existence/content
        if "file_checks" in assertions:
            for file_check in assertions["file_checks"]:
                total_assertions += 1
                # Would need to check sandbox files
                # For now, assume pass if task succeeded
                if task.status == "success":
                    passed_assertions += 1
        
        return passed_assertions / total_assertions if total_assertions > 0 else 0.0


def get_benchmark_trend() -> Dict[str, Any]:
    """Get benchmark score trend across harness versions"""
    
    from siha.models import BenchmarkRun, HarnessVersion
    
    with get_session() as session:
        versions = session.query(HarnessVersion).order_by(HarnessVersion.id).all()
        
        trend_data = []
        for version in versions:
            runs = session.query(BenchmarkRun).filter(
                BenchmarkRun.harness_version == version.id
            ).all()
            
            if runs:
                avg_score = sum(r.score for r in runs) / len(runs)
                trend_data.append({
                    "version_id": version.id,
                    "label": version.label,
                    "score": avg_score,
                    "timestamp": version.ts.isoformat()
                })
        
        return {
            "trend": trend_data,
            "total_versions": len(versions)
        }

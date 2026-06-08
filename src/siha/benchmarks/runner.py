"""Deterministic benchmark execution and scoring"""

from typing import Dict, Any
from siha.db import get_session
from siha.models import Benchmark, BenchmarkRun, HarnessVersion, BenchmarkOrigin, Step
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
            "assertion": {"exit_code": 0, "stdout_regex": r"\b55\b"},
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "file_io_write",
            "category": "file_io",
            "task_spec": {
                "prompt": "Create a file named test.txt with the content 'Hello World', then read it back and show the content",
                "sandbox": "local"
            },
            "assertion": {"exit_code": 0, "stdout_regex": "Hello World"},
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "list_directory",
            "category": "file_io",
            "task_spec": {
                "prompt": "List the contents of the current directory",
                "sandbox": "local"
            },
            "assertion": {"exit_code": 0, "stdout_regex": r"\."},
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "simple_math",
            "category": "math",
            "task_spec": {
                "prompt": "Calculate and print the result of 2 + 2",
                "sandbox": "local"
            },
            "assertion": {"exit_code": 0, "stdout_regex": r"\b4\b"},
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "shell_command",
            "category": "shell",
            "task_spec": {
                "prompt": "Run the command 'echo hello' and show the output",
                "sandbox": "local"
            },
            "assertion": {"exit_code": 0, "stdout_regex": "hello"},
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "json_sum",
            "category": "data_processing",
            "task_spec": {
                "prompt": "Parse this JSON {'values':[1,2,3,4]} and print the sum of values",
                "sandbox": "local"
            },
            "assertion": {"exit_code": 0, "stdout_regex": r"\b10\b"},
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "string_reverse",
            "category": "data_processing",
            "task_spec": {
                "prompt": "Write and run code that reverses the string 'stressed' and prints the result",
                "sandbox": "local"
            },
            "assertion": {"exit_code": 0, "stdout_regex": "desserts"},
            "origin": BenchmarkOrigin.seed
        },
        {
            "name": "web_fetch_example",
            "category": "web",
            "task_spec": {
                "prompt": "Fetch https://example.com and show the page title",
                "sandbox": "local"
            },
            "assertion": {"exit_code": 0, "stdout_regex": "Example Domain"},
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
        output_text = self._task_output_text(task.id)
        
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
                    "error_summary": task.error_summary,
                    "final_answer": task.final_answer,
                    "output_text": output_text,
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
        output_text = self._task_output_text(task.id)
        
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
            if re.search(assertions["stdout_regex"], output_text, flags=re.I | re.M):
                passed_assertions += 1
        
        # Check file existence/content
        if "file_checks" in assertions:
            for file_check in assertions["file_checks"]:
                total_assertions += 1
                path = file_check.get("path")
                pattern = file_check.get("content_regex")
                matched_path = not path or path in output_text
                matched_content = not pattern or re.search(pattern, output_text, flags=re.I | re.M)
                if matched_path and matched_content:
                    passed_assertions += 1
        
        return passed_assertions / total_assertions if total_assertions > 0 else 0.0

    def _task_output_text(self, task_id: int) -> str:
        """Collect observable output from final answers and observation steps."""
        chunks = []
        with get_session() as session:
            from siha.models import Task

            task = session.get(Task, task_id)
            if task and task.final_answer:
                chunks.append(task.final_answer)

            steps = session.query(Step).filter(Step.task_id == task_id).order_by(Step.idx).all()
            for step in steps:
                content = step.content or {}
                if isinstance(content, dict):
                    for key in ("output", "error", "content"):
                        value = content.get(key)
                        if value:
                            chunks.append(str(value))
                    data = content.get("data")
                    if data:
                        chunks.append(str(data))
        return "\n".join(chunks)


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

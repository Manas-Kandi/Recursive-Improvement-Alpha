"""Auto-generate benchmarks from novel tasks"""

from typing import Dict, Any, Optional
from siha.llm.factory import create_llm_client
from siha.llm.registry import get_model_for_role
from siha.db import get_session
from siha.models import Benchmark, BenchmarkOrigin, Task
from siha.agent.session import Session
import json


class BenchmarkGenerator:
    """Auto-generates benchmarks from novel task categories"""

    def __init__(self):
        self.client = create_llm_client(
            model=get_model_for_role("meta"),
        )
    
    def generate_from_task(self, task_id: int) -> Optional[Benchmark]:
        """Generate a benchmark from a completed task if it represents a novel category"""
        
        # Get task trace
        session = Session(task_id)
        trace = session.get_trace()
        
        # Classify task category
        category = self._classify_category(trace)
        
        # Check if this category already has benchmarks
        if self._category_exists(category):
            return None
        
        # Generate benchmark spec
        benchmark_spec = self._generate_benchmark_spec(trace, category)
        
        # Persist benchmark
        benchmark = self._persist_benchmark(benchmark_spec, category)
        
        return benchmark
    
    def _classify_category(self, trace: Dict[str, Any]) -> str:
        """Classify the task into a category"""
        
        prompt = f"""
Classify this task into one of these categories:
- math: mathematical calculations, algorithms
- file_io: reading/writing files, directory operations
- shell: executing shell commands
- web: web scraping, API calls
- data_processing: parsing, transforming data
- plotting: generating charts/visualizations

Task prompt: {trace['task']['prompt']}

Return just the category name.
"""
        
        response = self.client.chat([{"role": "user", "content": prompt}])
        category = response.choices[0].message.content.strip().lower()
        
        # Default to data_processing if unknown
        valid_categories = ["math", "file_io", "shell", "web", "data_processing", "plotting"]
        return category if category in valid_categories else "data_processing"
    
    def _category_exists(self, category: str) -> bool:
        """Check if benchmarks already exist for this category"""
        with get_session() as session:
            existing = session.query(Benchmark).filter(
                Benchmark.category == category
            ).first()
            return existing is not None
    
    def _generate_benchmark_spec(self, trace: Dict[str, Any], category: str) -> Dict[str, Any]:
        """Generate a deterministic benchmark spec from the task"""
        
        prompt = f"""
Convert this task into a deterministic benchmark specification.

Original task: {trace['task']['prompt']}
Category: {category}

Generate a JSON response with:
- name: unique benchmark name (snake_case)
- task_spec: 
  - prompt: a specific, deterministic version of the task
  - sandbox: sandbox mode to use
- assertion:
  - exit_code: expected exit code (0 for success)
  - stdout_regex: optional regex pattern to match in output
  - file_checks: optional list of files to check

The benchmark should be:
- Deterministic: same input always produces same output
- Testable: has clear pass/fail criteria
- Representative: captures the essence of the original task
"""
        
        response = self.client.chat([{"role": "user", "content": prompt}])
        
        try:
            content = response.choices[0].message.content
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end]
            return json.loads(json_str)
        except:
            # Fallback to simple spec
            return {
                "name": f"{category}_auto_{trace['task']['id']}",
                "task_spec": {
                    "prompt": trace['task']['prompt'],
                    "sandbox": "local"
                },
                "assertion": {
                    "exit_code": 0
                }
            }
    
    def _persist_benchmark(self, spec: Dict[str, Any], category: str) -> Benchmark:
        """Persist the generated benchmark"""
        
        with get_session() as session:
            benchmark = Benchmark(
                name=spec["name"],
                category=category,
                task_spec=spec["task_spec"],
                assertion=spec["assertion"],
                origin=BenchmarkOrigin.auto
            )
            session.add(benchmark)
            session.commit()
            session.refresh(benchmark)
            return benchmark

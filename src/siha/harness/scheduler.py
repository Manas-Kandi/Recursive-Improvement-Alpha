"""Background improvement and benchmark job scheduler"""

import threading
import time
from typing import Optional
from siha.db import get_session
from siha.models import Task, TaskStatus, Mutation, MutationStatus
from siha.harness.analyzer import Analyzer
from siha.harness.mutator import Mutator
from siha.harness.evaluator import Evaluator
from siha.config import settings


class Scheduler:
    """Background scheduler for improvement and benchmark jobs"""
    
    def __init__(self):
        self.analyzer = Analyzer()
        self.mutator = Mutator()
        self.evaluator = Evaluator()
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the background scheduler"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the background scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()
    
    def _run_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                # Check for completed tasks to analyze
                self._analyze_completed_tasks()
                
                # Check for pending mutations to evaluate
                self._evaluate_pending_mutations()
                
                # Sleep for interval
                time.sleep(settings.improve_interval_s)
            except Exception as e:
                print(f"Scheduler error: {e}")
                time.sleep(10)
    
    def _analyze_completed_tasks(self):
        """Analyze completed tasks that have not yet been analyzed."""
        from siha.portal.events import event_bus

        # Collect unanalyzed task ids first to avoid holding the session open
        # across LLM calls.
        with get_session() as session:
            tasks = session.query(Task).filter(
                Task.status == TaskStatus.success,
                Task.analyzed == False,  # noqa: E712
            ).order_by(Task.id).limit(10).all()
            task_ids = [t.id for t in tasks]

        for task_id in task_ids:
            try:
                critique = self.analyzer.analyze_task(task_id)

                for mutation_data in critique.get("proposed_mutations", []):
                    mutation = self.mutator.propose_mutation(mutation_data)
                    event_bus.publish("mutation_proposed", {"mutation_id": mutation.id})

                    if not settings.require_human_approval:
                        self.mutator.apply_mutation(mutation)

                # Optionally generate a benchmark from a novel task.
                self._maybe_generate_benchmark(task_id)
            finally:
                # Mark analyzed regardless of outcome to avoid reprocessing loops.
                with get_session() as session:
                    task = session.get(Task, task_id)
                    if task:
                        task.analyzed = True
                        session.commit()
                event_bus.publish("task_analyzed", {"task_id": task_id})

    def _maybe_generate_benchmark(self, task_id: int):
        """Generate a benchmark from a novel task category, if applicable."""
        try:
            from siha.benchmarks.generator import BenchmarkGenerator

            BenchmarkGenerator().generate_from_task(task_id)
        except Exception as e:
            print(f"Benchmark generation skipped: {e}")
    
    def _evaluate_pending_mutations(self):
        """Evaluate pending mutations against benchmarks"""
        with get_session() as session:
            pending_mutations = session.query(Mutation).filter(
                Mutation.status == MutationStatus.pending
            ).all()

            mutation_ids = [m.id for m in pending_mutations]

        for mutation_id in mutation_ids:
            with get_session() as session:
                mutation = session.get(Mutation, mutation_id)
                if not mutation or mutation.status != MutationStatus.pending:
                    continue

            self.mutator.apply_mutation(mutation)
            should_promote = self.evaluator.should_promote(mutation)

            with get_session() as session:
                mutation = session.get(Mutation, mutation_id)
                if not mutation:
                    continue
                if should_promote:
                    mutation.status = MutationStatus.active
                    session.commit()
                elif mutation.status != MutationStatus.reverted:
                    should_reject = True
                else:
                    should_reject = False

            if not should_promote and should_reject:
                self.mutator.rollback_mutation(mutation)
                with get_session() as session:
                    mutation = session.get(Mutation, mutation_id)
                    if mutation:
                        mutation.status = MutationStatus.rejected
                        session.commit()
    
    def trigger_improvement(self):
        """Manually trigger improvement cycle"""
        self._analyze_completed_tasks()
        self._evaluate_pending_mutations()

"""Background improvement and benchmark job scheduler."""

import threading
import time
from typing import Optional
from siha.db import get_session
from siha.models import Task, TaskStatus, TaskCategory, Mutation, MutationStatus
from sqlmodel import select
from siha.harness.analyzer import Analyzer
from siha.harness.mutator import Mutator
from siha.harness.evaluator import Evaluator
from siha.harness.synthesizer import TemplateSynthesizer
from siha.config import settings
from siha.logging import get_logger

logger = get_logger(__name__)


class Scheduler:
    """Background scheduler for improvement and benchmark jobs"""
    
    def __init__(self):
        self.analyzer = Analyzer()
        self.mutator = Mutator()
        self.evaluator = Evaluator()
        self.synthesizer = TemplateSynthesizer(mutator=self.mutator)
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
                logger.error("Scheduler error", exc_info=True, extra={"error": str(e)})
                time.sleep(10)
    
    def _analyze_completed_tasks(self):
        """Analyze finished tasks (successes AND failures) not yet analyzed.

        Successes feed the synthesis flywheel; failures feed triage and the
        meta-analyzer — failed traces are where the harness learns what it
        cannot yet do. Failed benchmark/system tasks are excluded: they re-run
        constantly and would drown the analyzer in duplicate traces.
        """
        from sqlalchemy import or_, and_
        from siha.portal.events import event_bus

        with get_session() as session:
            tasks = session.exec(select(Task).where(
                Task.analyzed == False,  # noqa: E712
                or_(
                    Task.status == TaskStatus.success,
                    and_(
                        Task.status == TaskStatus.failed,
                        Task.category == TaskCategory.user,
                    ),
                ),
            ).order_by(Task.id).limit(10)).all()
            analyzable = [(t.id, t.status) for t in tasks]

        for task_id, task_status in analyzable:
            critique = None
            try:
                if task_status == TaskStatus.success:
                    # Deterministic distillation first: if the LLM planner solved
                    # this task, generalize it into a reusable action template.
                    synth_mutation = self.synthesizer.synthesize_from_task(task_id)
                    if synth_mutation is not None:
                        event_bus.publish("mutation_proposed", {"mutation_id": synth_mutation.id})
                        if not settings.require_human_approval:
                            self.mutator.apply_mutation(synth_mutation)

                critique = self.analyzer.analyze_task(task_id)
                for mutation_data in critique.get("proposed_mutations", []):
                    mutation = self.mutator.propose_mutation(mutation_data)
                    event_bus.publish("mutation_proposed", {"mutation_id": mutation.id})

                    if not settings.require_human_approval:
                        self.mutator.apply_mutation(mutation)

                if task_status == TaskStatus.success:
                    self._maybe_generate_benchmark(task_id)
            except Exception as e:
                logger.error("Analyzer error", exc_info=True, extra={"task_id": task_id, "error": str(e)})
            finally:
                with get_session() as session:
                    task = session.get(Task, task_id)
                    if task:
                        task.analyzed = True
                        if critique is not None:
                            task.triage = critique
                        session.commit()
                event_bus.publish("task_analyzed", {
                    "task_id": task_id,
                    "failure_categories": (critique or {}).get("failure_categories", []),
                })

    def _maybe_generate_benchmark(self, task_id: int):
        """Generate a benchmark from a novel task category, if applicable."""
        try:
            from siha.benchmarks.generator import BenchmarkGenerator

            BenchmarkGenerator().generate_from_task(task_id)
        except Exception as e:
            logger.warning("Benchmark generation skipped", extra={"task_id": task_id, "error": str(e)})

    def _evaluate_pending_mutations(self):
        """Evaluate candidate mutations against benchmarks and promote or rollback."""
        # ``evaluating`` is included so mutations orphaned by a crash
        # mid-evaluation are retried instead of being stuck forever.
        evaluable = (MutationStatus.candidate, MutationStatus.evaluating)
        with get_session() as session:
            candidate_mutations = session.exec(select(Mutation).where(
                Mutation.status.in_(evaluable),
            )).all()
            mutation_ids = [m.id for m in candidate_mutations]

        for mutation_id in mutation_ids:
            try:
                with get_session() as session:
                    mutation = session.get(Mutation, mutation_id)
                    if not mutation or mutation.status not in evaluable:
                        continue

                should_promote = self.evaluator.should_promote(mutation)

                if should_promote:
                    self.mutator.promote_mutation(mutation)
                else:
                    self.mutator.rollback_mutation(mutation)
            except Exception as e:
                logger.error("Evaluator error", exc_info=True, extra={"mutation_id": mutation_id, "error": str(e)})

    def trigger_improvement(self):
        """Manually trigger improvement cycle"""
        self._analyze_completed_tasks()
        self._evaluate_pending_mutations()

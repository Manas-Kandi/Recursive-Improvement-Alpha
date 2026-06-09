"""Template synthesis — distill LLM-planned successes into deterministic templates.

This is the core of the self-improvement flywheel: when a request falls
through the template layer and the LLM planner solves it successfully, the
synthesizer generalizes the (prompt, tool call) pair into a reusable
``ActionTemplate``. The next time a similar request arrives, the harness
handles it deterministically — no LLM, no latency, no cost.

The synthesis is fully deterministic (no LLM involved): argument values are
located inside the original prompt and replaced with regex capture groups.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from siha.db import get_session
from siha.models import (
    Task, Step, StepType, TaskStatus, TaskCategory,
    Mutation, MutationKind, TemplateOrigin,
    Benchmark, BenchmarkOrigin,
)
from sqlmodel import select
from siha.agent.action_mapper import ActionMapper
from siha.harness.mutator import Mutator
from siha.logging import get_logger

logger = get_logger(__name__)

# Prompts longer than this produce overly specific, brittle patterns.
MAX_PROMPT_LENGTH = 200

# Capture group used for short token-like values (paths, names).
_TOKEN_GROUP = r'([\w\-./]+)'
# Capture group used for free-text values (content, queries).
_TEXT_GROUP = r'(.+)'


class TemplateSynthesizer:
    """Generalizes successful planner-sourced tool calls into action templates."""

    def __init__(self, mutator: Optional[Mutator] = None):
        self.mutator = mutator or Mutator()

    def synthesize_from_task(self, task_id: int) -> Optional[Mutation]:
        """Inspect a completed task; if the planner solved it, propose a template.

        Returns the proposed Mutation, or None if no template could be derived.
        """
        with get_session() as session:
            task = session.get(Task, task_id)
            if not task or task.status != TaskStatus.success:
                return None
            if task.category != TaskCategory.user:
                return None
            prompt = task.user_prompt

            steps = session.exec(select(Step).where(
                Step.task_id == task_id,
            ).order_by(Step.idx)).all()

        if len(prompt) > MAX_PROMPT_LENGTH:
            return None

        planned_call = self._find_successful_planned_call(steps)
        if not planned_call:
            return None

        tool_name, tool_args = planned_call

        # Skip if the active template set already covers this prompt.
        mapper = ActionMapper()
        if mapper.map(prompt):
            return None

        derived = self.generalize(prompt, tool_name, tool_args)
        if not derived:
            return None

        pattern, args_template = derived
        name = f"synth_{tool_name}_{task_id}"

        mutation = self.mutator.propose_mutation({
            "kind": MutationKind.template,
            "target": name,
            "before": {},
            "after": {
                "name": name,
                "pattern": pattern,
                "tool_name": tool_name,
                "args_template": args_template,
                "priority": 80,
                "example": prompt,
                "origin": TemplateOrigin.synthesized,
                "source_task_id": task_id,
            },
            "rationale": (
                f"Task {task_id} required LLM planning but succeeded with a single "
                f"{tool_name} call. Distilled into a deterministic template so similar "
                "requests bypass the LLM."
            ),
        })
        # Every learned template ships with its own regression benchmark so
        # the evaluation suite grows together with capability.
        self._create_regression_benchmark(task_id, prompt, tool_name, tool_args)

        logger.info(
            "Template synthesized from task",
            extra={"task_id": task_id, "template": name, "pattern": pattern},
        )
        return mutation

    @staticmethod
    def _create_regression_benchmark(
        task_id: int,
        prompt: str,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Optional[Benchmark]:
        """Persist a deterministic benchmark derived from the source task.

        Assertions are grounded in observable effects (files on disk) where
        possible, falling back to a clean exit.
        """
        name = f"regression_synth_{task_id}"
        assertion: Dict[str, Any] = {"exit_code": 0}

        if tool_name == "write_file" and tool_args.get("path"):
            file_check: Dict[str, Any] = {"path": tool_args["path"]}
            content = tool_args.get("content")
            if isinstance(content, str) and content.strip():
                # Match on a stable prefix of the content.
                snippet = content.strip()[:60]
                file_check["content_regex"] = re.escape(snippet)
            assertion["file_checks"] = [file_check]
        elif tool_name == "run_shell":
            command = tool_args.get("command", "")
            mkdir_match = re.match(r"mkdir\s+(?:-p\s+)?([\w\-./]+)", command)
            if mkdir_match:
                assertion["file_checks"] = [{"path": mkdir_match.group(1)}]

        try:
            with get_session() as session:
                existing = session.exec(select(Benchmark).where(
                    Benchmark.name == name,
                )).first()
                if existing:
                    return existing
                benchmark = Benchmark(
                    name=name,
                    category="regression",
                    task_spec={"prompt": prompt, "sandbox": "local"},
                    assertion=assertion,
                    origin=BenchmarkOrigin.auto,
                )
                session.add(benchmark)
                session.commit()
                session.refresh(benchmark)
                return benchmark
        except Exception:
            logger.warning("Failed to create regression benchmark", extra={"task_id": task_id})
            return None

    @staticmethod
    def _find_successful_planned_call(steps: List[Step]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Locate the first planner-sourced tool call that succeeded."""
        planned: Optional[Tuple[str, Dict[str, Any]]] = None
        awaiting_observation = False

        for step in steps:
            content = step.content or {}
            if step.type == StepType.tool_call and content.get("source") == "planned":
                calls = content.get("tool_calls") or []
                if not calls:
                    continue
                fn = calls[0].get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue
                planned = (fn.get("name", ""), args)
                awaiting_observation = True
            elif step.type == StepType.observation and awaiting_observation:
                if content.get("success"):
                    return planned
                planned = None
                awaiting_observation = False

        return None

    @staticmethod
    def generalize(
        prompt: str,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Turn a concrete (prompt, args) pair into (regex pattern, args_template).

        Each string argument value found inside the prompt is replaced by a
        capture group; the args template references groups via {n} placeholders.
        Returns None when no argument value appears in the prompt (the request
        is not generalizable by substitution).
        """
        prompt_lower = prompt.lower()

        # Locate each string arg value inside the prompt (longest values first
        # so nested values don't shadow each other).
        locations: List[Tuple[int, int, str, str]] = []  # (start, end, arg_key, value)
        claimed: List[Tuple[int, int]] = []
        arg_items = sorted(
            ((k, v) for k, v in tool_args.items() if isinstance(v, str) and v.strip()),
            key=lambda kv: -len(kv[1]),
        )
        for key, value in arg_items:
            idx = prompt_lower.find(value.lower().strip())
            if idx < 0:
                continue
            span = (idx, idx + len(value.strip()))
            if any(span[0] < c[1] and c[0] < span[1] for c in claimed):
                continue
            claimed.append(span)
            locations.append((span[0], span[1], key, value.strip()))

        if not locations:
            return None

        # Build the regex left-to-right, assigning group numbers in order.
        locations.sort(key=lambda loc: loc[0])
        pattern_parts: List[str] = []
        group_for_key: Dict[str, int] = {}
        cursor = 0
        for group_idx, (start, end, key, value) in enumerate(locations, start=1):
            literal = prompt_lower[cursor:start]
            pattern_parts.append(TemplateSynthesizer._flexible_escape(literal))
            # Token-like values get a tight group; free text gets a greedy one.
            group = _TOKEN_GROUP if re.fullmatch(r"[\w\-./]+", value) else _TEXT_GROUP
            pattern_parts.append(group)
            group_for_key[key] = group_idx
            cursor = end
        pattern_parts.append(TemplateSynthesizer._flexible_escape(prompt_lower[cursor:]))

        pattern = "".join(pattern_parts).strip()
        if not pattern:
            return None

        # Validate the generated pattern compiles and round-trips on the prompt.
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return None
        if not compiled.search(prompt_lower):
            return None

        args_template: Dict[str, Any] = {}
        for key, value in tool_args.items():
            if key in group_for_key:
                args_template[key] = f"{{{group_for_key[key]}}}"
            else:
                args_template[key] = value

        return pattern, args_template

    @staticmethod
    def _flexible_escape(literal: str) -> str:
        """Escape literal text but tolerate flexible whitespace and articles."""
        escaped = re.escape(literal)
        # Collapse escaped whitespace runs into \s+
        escaped = re.sub(r"(\\\s|\s)+", r"\\s+", escaped)
        return escaped

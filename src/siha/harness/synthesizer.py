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

# Tokens shorter than this or in this set are skipped during token-level generalization.
_STOP_WORDS = {
    "a", "an", "the", "to", "of", "in", "on", "at", "is", "it",
    "and", "or", "for", "with", "as", "by", "from", "up", "down",
}


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
        When the whole value is not present, individual tokens are searched and
        generalised.  Returns None when no argument value appears in the prompt.
        """
        prompt_lower = prompt.lower()

        locations: List[Tuple[int, int, str, str]] = []  # (start, end, arg_key, token)
        claimed: List[Tuple[int, int]] = []
        whole_replaced_keys: set = set()
        token_group_map: Dict[str, Dict[str, int]] = {}  # arg_key -> token -> group_num

        arg_items = sorted(
            ((k, v) for k, v in tool_args.items() if isinstance(v, str) and v.strip()),
            key=lambda kv: -len(kv[1]),
        )
        for key, value in arg_items:
            value_lower = value.lower().strip()

            # 1) Whole-value match
            idx = prompt_lower.find(value_lower)
            if idx >= 0:
                span = (idx, idx + len(value_lower))
                if not any(span[0] < c[1] and c[0] < span[1] for c in claimed):
                    claimed.append(span)
                    locations.append((span[0], span[1], key, value_lower))
                    whole_replaced_keys.add(key)
                continue

            # 2) Token-level fallback
            original_tokens = value.strip().split()
            found_tokens: Dict[str, int] = {}
            for token in original_tokens:
                token_clean = token.strip(".,;:!?").lower()
                if len(token_clean) < 3 or token_clean in _STOP_WORDS:
                    continue
                tidx = prompt_lower.find(token_clean)
                if tidx < 0:
                    continue
                span = (tidx, tidx + len(token_clean))
                if any(span[0] < c[1] and c[0] < span[1] for c in claimed):
                    continue
                claimed.append(span)
                locations.append((span[0], span[1], key, token_clean))
                found_tokens[token] = len(locations)

            if found_tokens:
                token_group_map[key] = found_tokens

        if not locations:
            return None

        # Build the regex left-to-right, assigning group numbers in order.
        locations.sort(key=lambda loc: loc[0])
        pattern_parts: List[str] = []
        group_for_key: Dict[str, int] = {}
        token_to_group: Dict[Tuple[str, str], int] = {}
        cursor = 0
        for group_idx, (start, end, key, token) in enumerate(locations, start=1):
            literal = prompt_lower[cursor:start]
            pattern_parts.append(TemplateSynthesizer._flexible_escape(literal))
            group = _TOKEN_GROUP if re.fullmatch(r"[\w\-./]+", token) else _TEXT_GROUP
            pattern_parts.append(group)
            if key in whole_replaced_keys:
                group_for_key[key] = group_idx
            else:
                token_to_group[(key, token)] = group_idx
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
            if key in whole_replaced_keys:
                args_template[key] = f"{{{group_for_key[key]}}}"
            elif key in token_group_map:
                rendered = str(value)
                for orig_token, _ in token_group_map[key].items():
                    token_clean = orig_token.lower().strip(".,;:!?")
                    group_num = token_to_group.get((key, token_clean))
                    if group_num is not None:
                        rendered = rendered.replace(orig_token, f"{{{group_num}}}")
                args_template[key] = rendered
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

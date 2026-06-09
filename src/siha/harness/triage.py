"""Rule-based trace triage — deterministic failure taxonomy.

Most task traces don't need a large language model to critique: the failure
modes are recognizable patterns (missing file, blocked command, unknown tool,
timeout, exhausted step budget). The triage layer classifies these locally and
deterministically; the LLM analyzer is reserved for traces the rules cannot
explain. This keeps the self-improvement loop functional fully offline.
"""

import re
from typing import Any, Dict, List, Optional


# (regex on tool error text, root cause label, what to do about it)
_ERROR_TAXONOMY = [
    (
        r"No such file or directory|FileNotFoundError|does not exist",
        "missing_path",
        "A tool call referenced a path that does not exist. Likely a path "
        "resolution issue: the harness should ground relative paths in the "
        "workspace index before executing.",
    ),
    (
        r"Blocked unsafe command",
        "safety_block",
        "The safety guard rejected a command. This is correct behaviour; no "
        "mutation needed. If the task legitimately requires this operation it "
        "must be performed manually.",
    ),
    (
        r"Tool not found",
        "unknown_tool",
        "The planner selected a tool that is not registered. The planner "
        "prompt should enumerate available tools more clearly, or grammar-"
        "constrained decoding should be enabled for the local provider.",
    ),
    (
        r"timed out|TimeoutExpired|timeout",
        "timeout",
        "A tool call exceeded its time budget. Consider raising timeout_s for "
        "long-running operations or breaking work into smaller steps.",
    ),
    (
        r"Permission denied|EACCES",
        "permission_denied",
        "A tool call hit a filesystem permission error inside the sandbox.",
    ),
    (
        r"JSONDecodeError|Failed to parse|Expecting value",
        "malformed_output",
        "A model emitted malformed structured output. Grammar-constrained "
        "decoding eliminates this for the local provider.",
    ),
    (
        r"Step budget .* exhausted",
        "step_budget_exhausted",
        "The agent looped without converging. The task likely needs a better "
        "first-step plan or a new action template.",
    ),
]


class TraceTriage:
    """Classifies task traces deterministically before any LLM is consulted."""

    def triage(self, trace: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return a critique dict (analyzer-compatible) or None if the LLM is needed.

        Returns a critique with ``proposed_mutations: []`` for traces that are
        healthy or whose failures are fully explained by the taxonomy. Returns
        None only when the trace contains failures the rules cannot classify.
        """
        task = trace.get("task", {})
        tool_calls = trace.get("tool_calls", [])
        steps = trace.get("steps", [])

        failures = [tc for tc in tool_calls if not tc.get("success")]

        # Healthy template-driven success: nothing for an LLM to improve.
        if task.get("status") == "success" and not failures:
            return {
                "root_cause": None,
                "what_went_well": self._successes(tool_calls, steps),
                "proposed_mutations": [],
                "triage": "healthy",
            }

        # Classify every failure against the taxonomy.
        classified: List[Dict[str, str]] = []
        for failure in failures:
            error_text = self._failure_text(failure, steps)
            label, explanation = self._classify(error_text)
            if label is None:
                # Unrecognized failure — defer to the LLM analyzer.
                return None
            classified.append({
                "tool_id": failure.get("tool_id"),
                "category": label,
                "explanation": explanation,
            })

        if not classified and task.get("status") != "success":
            # Failed task with no failed tool calls (e.g. step budget, crash):
            # check the error summary.
            error_summary = task.get("error_summary") or ""
            label, explanation = self._classify(error_summary)
            if label is None:
                return None
            classified.append({
                "tool_id": None,
                "category": label,
                "explanation": explanation,
            })

        return {
            "root_cause": "; ".join(
                f"{c['category']}: {c['explanation']}" for c in classified
            ) or None,
            "what_went_well": self._successes(tool_calls, steps),
            "proposed_mutations": [],
            "triage": "classified",
            "failure_categories": [c["category"] for c in classified],
        }

    @staticmethod
    def _classify(error_text: str):
        for pattern, label, explanation in _ERROR_TAXONOMY:
            if re.search(pattern, error_text or "", re.IGNORECASE):
                return label, explanation
        return None, None

    @staticmethod
    def _failure_text(failure: Dict[str, Any], steps: List[Dict[str, Any]]) -> str:
        result = failure.get("result") or {}
        parts = [str(result.get("error") or ""), str(result.get("output") or "")]
        return " ".join(p for p in parts if p)

    @staticmethod
    def _successes(tool_calls: List[Dict[str, Any]], steps: List[Dict[str, Any]]) -> List[str]:
        wins = []
        succeeded = [tc for tc in tool_calls if tc.get("success")]
        if succeeded:
            wins.append(f"{len(succeeded)} tool call(s) executed successfully")
        if any((s.get("content") or {}).get("source") == "template" for s in steps):
            wins.append("request was resolved deterministically by the template layer")
        return wins

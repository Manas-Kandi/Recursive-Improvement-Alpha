"""Task Planner — converts a user request into a concrete first tool call.

Used as a pre-step before the main ReAct loop. The planner asks a small
model: "given this task and these tools, what is the FIRST action to take?"
The result is injected as a pre-seeded assistant message so the main model
never sees the ambiguous user request — it only sees "here is what to do next."
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from siha.config import settings


class TaskPlanner:
    """Generates a concrete first-step plan from a user prompt + tool list."""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        from siha.llm.factory import create_llm_client
        self.client = create_llm_client(model=model, provider=provider)

    def plan_first_step(
        self,
        user_prompt: str,
        tools: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Return the first tool call to make, or None if planning fails."""

        tool_descriptions = "\n".join(
            f'- {t["function"]["name"]}: {t["function"]["description"]}  '
            f'args: {list(t["function"].get("parameters", {}).get("properties", {}).keys())}'
            for t in tools
        )

        prompt = (
            "You are a task planner. Given a user request and a list of available tools, "
            "output the FIRST tool call needed to begin completing the task.\n\n"
            f"User request: {user_prompt}\n\n"
            "Available tools:\n"
            f"{tool_descriptions}\n\n"
            "Output ONLY a single JSON object like:\n"
            '{"tool": "tool_name", "arguments": {"arg1": "value1"}}\n'
            "No explanation. No markdown. Just the JSON."
        )

        try:
            if hasattr(self.client, "chat_constrained"):
                # Grammar-constrained decoding: the local model physically
                # cannot emit a malformed tool call.
                from siha.llm.grammar import build_tool_call_grammar

                grammar = build_tool_call_grammar(tools)
                response = self.client.chat_constrained(
                    [{"role": "user", "content": prompt}],
                    grammar,
                    temperature=0.1,
                    max_tokens=256,
                )
            else:
                response = self.client.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=256,
                )
            raw = response.choices[0].message.content.strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(
                    ln for ln in lines
                    if not ln.startswith("```")
                ).strip()

            data = json.loads(raw)
            tool_name = data.get("tool") or data.get("name")
            arguments = data.get("arguments") or data.get("args") or {}

            if not tool_name:
                return None

            return {
                "id": f"plan-{tool_name}-0",
                "type": "function",
                "function": {"name": tool_name, "arguments": json.dumps(arguments)},
            }

        except Exception:
            return None

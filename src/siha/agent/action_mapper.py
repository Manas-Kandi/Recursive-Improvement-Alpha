"""Action Mapper — deterministic template engine that maps user requests
directly to tool calls without any LLM reasoning.

This is the "harness is smart" layer. Common tasks are handled by regex
patterns and template substitution. The LLM is only consulted for truly
novel requests that don't match any template.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# Template registry: (regex_pattern, tool_name, argument_builder)
# Each entry maps a user utterance pattern to a concrete tool call.
ACTION_TEMPLATES: List[Tuple[str, str, callable]] = [
    # File / directory creation
    (
        r'(?:create|make)\s+(?:a\s+)?(?:new\s+)?folder\s+(?:called\s+|named\s+)?["\']?(\w+)["\']?',
        "run_shell",
        lambda m: {"command": f"mkdir -p {m.group(1)}"},
    ),
    (
        r'(?:create|make|write)\s+(?:a\s+)?(?:new\s+)?file\s+(?:called\s+|named\s+)?["\']?([^"\']+)["\']?\s+with\s+(?:content\s+)?(.+)',
        "write_file",
        lambda m: {"path": m.group(1).strip(), "content": m.group(2).strip()},
    ),
    # Move / copy / rename
    (
        r'(?:move|mv)\s+(?:this\s+)?(?:file\s+)?["\']?([^"\']+)["\']?\s+(?:to\s+|in\s+(?:the\s+)?folder\s+)?["\']?([^"\']+)["\']?',
        "run_shell",
        lambda m: {"command": f"mv {m.group(1).strip()} {m.group(2).strip()}/"},
    ),
    (
        r'(?:copy|cp)\s+(?:this\s+)?(?:file\s+)?["\']?([^"\']+)["\']?\s+(?:to\s+)?["\']?([^"\']+)["\']?',
        "run_shell",
        lambda m: {"command": f"cp {m.group(1).strip()} {m.group(2).strip()}"},
    ),
    (
        r'(?:rename)\s+(?:this\s+)?(?:file\s+)?["\']?([^"\']+)["\']?\s+(?:to\s+)?["\']?([^"\']+)["\']?',
        "run_shell",
        lambda m: {"command": f"mv {m.group(1).strip()} {m.group(2).strip()}"},
    ),
    # List / read
    (
        r'(?:list|ls|show)\s+(?:the\s+)?(?:contents\s+of\s+)?["\']?([^"\']+)["\']?',
        "list_dir",
        lambda m: {"path": m.group(1).strip()},
    ),
    (
        r'(?:read|open|cat|show)\s+(?:the\s+)?(?:file\s+)?["\']?([^"\']+)["\']?',
        "read_file",
        lambda m: {"path": m.group(1).strip()},
    ),
    # Delete
    (
        r'(?:delete|remove|rm)\s+(?:the\s+)?(?:file\s+|folder\s+)?["\']?([^"\']+)["\']?',
        "run_shell",
        lambda m: {"command": f"rm -rf {m.group(1).strip()}"},
    ),
    # Code execution
    (
        r'(?:run|execute)\s+(?:this\s+)?(?:python\s+)?code:?\s*(.+)?',
        "run_python",
        lambda m: {"code": m.group(1).strip() if m.group(1) else ""},
    ),
    (
        r'(?:run|execute)\s+(?:this\s+)?(?:shell\s+|command\s+)?["\']?([^"\']+)["\']?',
        "run_shell",
        lambda m: {"command": m.group(1).strip()},
    ),
    # Search
    (
        r'(?:search|find|look\s+up)\s+(?:for\s+)?["\']?(.+)["\']?',
        "web_search",
        lambda m: {"query": m.group(1).strip()},
    ),
]


class ActionMapper:
    """Deterministic mapping from user request to tool call."""

    def map(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        """Try to match user prompt against templates. Returns tool call dict or None."""
        prompt_lower = user_prompt.lower()

        for pattern, tool_name, arg_builder in ACTION_TEMPLATES:
            match = re.search(pattern, prompt_lower, re.IGNORECASE)
            if match:
                arguments = arg_builder(match)
                return {
                    "id": f"map-{tool_name}-0",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(arguments),
                    },
                }
        return None

    @property
    def template_count(self) -> int:
        return len(ACTION_TEMPLATES)

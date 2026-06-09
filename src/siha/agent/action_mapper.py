"""Action Mapper — deterministic template engine that maps user requests
directly to tool calls without any LLM reasoning.

This is the "harness is smart" layer. Common tasks are handled by regex
patterns and template substitution. The LLM is only consulted for truly
novel requests that don't match any template.

Templates live in the database (``ActionTemplate``) so that the
self-improvement loop can propose, evaluate, promote, and roll back new
templates exactly like prompts and tools. Matching is priority-ordered and
span-claiming: once a region of the prompt is claimed by a template, lower
priority templates cannot re-match the same text. This supports compound
requests ("create folder X and write file Y") without firing overlapping
duplicates.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TemplateSpec:
    """In-memory representation of an action template."""

    name: str
    pattern: str
    tool_name: str
    args_template: Dict[str, Any]
    priority: int = 100
    template_id: Optional[int] = None


# Seed templates. These are loaded into the DB by ``seed_default_templates``
# and also serve as the in-memory fallback when the DB is unavailable.
# Lower priority numbers are matched first.
DEFAULT_TEMPLATES: List[TemplateSpec] = [
    TemplateSpec(
        name="create_folder",
        pattern=r'(?:create|make)\s+(?:a\s+)?(?:new\s+)?folder\s+(?:called\s+|named\s+)\s*["\']?([\w\-/]+)["\']?',
        tool_name="run_shell",
        args_template={"command": "mkdir -p {1}"},
        priority=10,
    ),
    TemplateSpec(
        name="write_named_file_with_content",
        pattern=r'(?:create|make|write)\s+(?:a\s+)?(?:new\s+)?(?:\w+\s+)?([\w\-/]+\.\w+)\s+file\b.*?\s+with\s+(?:content\s+)?(.+)',
        tool_name="write_file",
        args_template={"path": "{1}", "content": "{2}"},
        priority=20,
    ),
    TemplateSpec(
        name="write_file_called_with_content",
        pattern=r'(?:create|make|write)\s+(?:a\s+)?(?:new\s+)?(?:\w+\s+)?file\s+(?:called\s+|named\s+)?["\']?([^"\']+?)["\']?\s+with\s+(?:content\s+)?(.+)',
        tool_name="write_file",
        args_template={"path": "{1}", "content": "{2}"},
        priority=21,
    ),
    TemplateSpec(
        name="write_bare_file",
        pattern=r'(?:create|make|write)\s+(?:a\s+)?(?:new\s+)?(?:\w+\s+)?file\s+(?:called\s+|named\s+)?["\']?([^"\']+\.\w+)["\']?\b(?!\s+with)',
        tool_name="write_file",
        args_template={"path": "{1}", "content": "# Generated file\n"},
        priority=30,
    ),
    TemplateSpec(
        name="move_file",
        pattern=r'(?:move|mv)\s+(?:this\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?\s+(?:to\s+|into\s+|in\s+(?:the\s+)?folder\s+)["\']?([^\s"\']+)["\']?',
        tool_name="run_shell",
        args_template={"command": "mv {1} {2}"},
        priority=40,
    ),
    TemplateSpec(
        name="copy_file",
        pattern=r'(?:copy|cp)\s+(?:this\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?\s+(?:to\s+)?["\']?([^\s"\']+)["\']?',
        tool_name="run_shell",
        args_template={"command": "cp {1} {2}"},
        priority=41,
    ),
    TemplateSpec(
        name="rename_file",
        pattern=r'rename\s+(?:this\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?\s+(?:to\s+)?["\']?([^\s"\']+)["\']?',
        tool_name="run_shell",
        args_template={"command": "mv {1} {2}"},
        priority=42,
    ),
    TemplateSpec(
        name="list_directory",
        pattern=r'(?:list|ls)\s+(?:the\s+)?(?:contents\s+of\s+)?["\']?([^\s"\']+)["\']?',
        tool_name="list_dir",
        args_template={"path": "{1}"},
        priority=50,
    ),
    TemplateSpec(
        name="read_file",
        pattern=r'(?:read|open|cat|show)\s+(?:the\s+)?(?:file\s+)?["\']?([^\s"\']+\.\w+)["\']?',
        tool_name="read_file",
        args_template={"path": "{1}"},
        priority=51,
    ),
    TemplateSpec(
        name="delete_path",
        pattern=r'(?:delete|remove|rm)\s+(?:the\s+)?(?:file\s+|folder\s+)?["\']?([^\s"\']+)["\']?',
        tool_name="run_shell",
        args_template={"command": "rm -rf {1}"},
        priority=60,
    ),
    TemplateSpec(
        name="run_python_code",
        pattern=r'(?:run|execute)\s+(?:this\s+)?(?:python\s+)?code:?\s*(.+)',
        tool_name="run_python",
        args_template={"code": "{1}"},
        priority=70,
    ),
    TemplateSpec(
        name="run_shell_command",
        pattern=r'(?:run|execute)\s+(?:this\s+)?(?:shell\s+|the\s+)?command\s+["\']?([^"\']+)["\']?',
        tool_name="run_shell",
        args_template={"command": "{1}"},
        priority=71,
    ),
    TemplateSpec(
        name="web_search",
        pattern=r'(?:search|look\s+up)\s+(?:the\s+web\s+)?(?:for\s+)?["\']?(.+?)["\']?$',
        tool_name="web_search",
        args_template={"query": "{1}"},
        priority=90,
    ),
]


_PLACEHOLDER_RE = re.compile(r"\{(\d+)\}")


def render_args(args_template: Dict[str, Any], match: "re.Match") -> Dict[str, Any]:
    """Substitute {1}, {2}, ... placeholders with regex capture groups."""

    def _render_value(value: Any) -> Any:
        if isinstance(value, str):
            def _sub(m: "re.Match") -> str:
                group_idx = int(m.group(1))
                try:
                    captured = match.group(group_idx)
                except (IndexError, re.error):
                    return ""
                return (captured or "").strip()

            return _PLACEHOLDER_RE.sub(_sub, value)
        if isinstance(value, dict):
            return {k: _render_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_render_value(v) for v in value]
        return value

    return {k: _render_value(v) for k, v in args_template.items()}


def seed_default_templates() -> None:
    """Seed the default action templates into the DB if they don't exist."""
    from siha.db import get_session
    from siha.models import ActionTemplate, TemplateOrigin, TemplateStatus
    from sqlmodel import select

    with get_session() as session:
        for spec in DEFAULT_TEMPLATES:
            existing = session.exec(select(ActionTemplate).where(
                ActionTemplate.name == spec.name,
            )).first()
            if not existing:
                session.add(ActionTemplate(
                    name=spec.name,
                    pattern=spec.pattern,
                    tool_name=spec.tool_name,
                    args_template=spec.args_template,
                    priority=spec.priority,
                    status=TemplateStatus.active,
                    origin=TemplateOrigin.seed,
                ))
        session.commit()


class ActionMapper:
    """Deterministic mapping from user request to tool call(s).

    Templates are loaded from the database (honouring an optional pinned
    harness version) with an in-memory fallback to ``DEFAULT_TEMPLATES``.
    """

    def __init__(self, harness_version_id: Optional[int] = None):
        self.harness_version_id = harness_version_id
        self._templates: List[TemplateSpec] = self._load_templates()

    def _load_templates(self) -> List[TemplateSpec]:
        """Load active (or version-pinned) templates from the DB."""
        try:
            from siha.db import get_session
            from siha.models import ActionTemplate, TemplateStatus, HarnessVersion
            from sqlmodel import select
            from sqlalchemy.exc import OperationalError

            try:
                with get_session() as session:
                    query = select(ActionTemplate)
                    if self.harness_version_id is not None:
                        version = session.get(HarnessVersion, self.harness_version_id)
                        if version and version.template_set:
                            query = query.where(ActionTemplate.id.in_(version.template_set))
                        else:
                            query = query.where(ActionTemplate.status == TemplateStatus.active)
                    else:
                        query = query.where(ActionTemplate.status == TemplateStatus.active)

                    rows = session.exec(query).all()
            except OperationalError:
                rows = []
        except Exception:
            rows = []

        if not rows:
            return sorted(DEFAULT_TEMPLATES, key=lambda t: t.priority)

        specs = [
            TemplateSpec(
                name=row.name,
                pattern=row.pattern,
                tool_name=row.tool_name,
                args_template=row.args_template or {},
                priority=row.priority,
                template_id=row.id,
            )
            for row in rows
        ]
        return sorted(specs, key=lambda t: t.priority)

    def map(self, user_prompt: str) -> List[Dict[str, Any]]:
        """Match templates against the prompt, first-match-wins per text span.

        Templates are tried in priority order. A region of the prompt claimed
        by one template cannot be re-matched by a lower-priority template, so
        overlapping templates produce exactly one tool call per intent.
        """
        prompt_lower = user_prompt.lower()
        claimed: List[Tuple[int, int]] = []
        matched: List[Tuple[int, TemplateSpec, Dict[str, Any]]] = []

        for spec in self._templates:
            try:
                compiled = re.compile(spec.pattern, re.IGNORECASE)
            except re.error:
                continue
            for match in compiled.finditer(prompt_lower):
                span = match.span()
                if span[0] == span[1]:
                    continue
                if any(self._overlaps(span, c) for c in claimed):
                    continue
                arguments = render_args(spec.args_template, match)
                claimed.append(span)
                matched.append((span[0], spec, arguments))

        # Order steps by their position in the prompt, not template priority,
        # so compound requests execute in the order the user stated them.
        matched.sort(key=lambda item: item[0])

        steps: List[Dict[str, Any]] = []
        hit_ids: List[int] = []
        for idx, (_pos, spec, arguments) in enumerate(matched):
            steps.append({
                "id": f"map-{spec.tool_name}-{idx}",
                "type": "function",
                "function": {
                    "name": spec.tool_name,
                    "arguments": json.dumps(arguments),
                },
                "template_name": spec.name,
            })
            if spec.template_id is not None:
                hit_ids.append(spec.template_id)

        if hit_ids:
            self._record_hits(hit_ids)

        return steps

    @staticmethod
    def _overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        return a[0] < b[1] and b[0] < a[1]

    def _record_hits(self, template_ids: List[int]) -> None:
        """Best-effort hit counting for template usage analytics."""
        try:
            from siha.db import get_session
            from siha.models import ActionTemplate

            with get_session() as session:
                for tid in template_ids:
                    row = session.get(ActionTemplate, tid)
                    if row:
                        row.hit_count = (row.hit_count or 0) + 1
                session.commit()
        except Exception:
            pass

    @property
    def template_count(self) -> int:
        return len(self._templates)

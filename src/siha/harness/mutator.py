"""Propose, apply, promote, and rollback mutations with candidate lifecycle."""

from typing import Dict, Any, Optional
from siha.db import get_session
from siha.models import (
    Prompt, PromptRole, PromptStatus, Strategy, StrategyStatus,
    Tool, ToolKind, ToolStatus,
    Mutation, MutationStatus, MutationKind, HarnessVersion
)
from datetime import datetime, timezone


class Mutator:
    """Manages mutation lifecycle: propose → candidate → promote/rollback."""

    def propose_mutation(self, mutation_data: Dict[str, Any]) -> Mutation:
        """Create a proposed mutation from analysis results."""
        before = mutation_data.get("before", {})
        after = mutation_data.get("after", {})
        if isinstance(before, str):
            before = {"text": before}
        if isinstance(after, str):
            after = {"text": after}

        with get_session() as session:
            mutation = Mutation(
                kind=mutation_data["kind"],
                target_id=mutation_data.get("target_id", 0),
                target_name=mutation_data.get("target") or mutation_data.get("target_name"),
                before=before,
                after=after,
                rationale=mutation_data.get("rationale", ""),
                status=MutationStatus.proposed,
            )
            session.add(mutation)
            session.commit()
            session.refresh(mutation)
            return mutation

    def apply_mutation(self, mutation: Mutation) -> HarnessVersion:
        """Apply a mutation as a candidate and create a candidate harness version."""
        with get_session() as session:
            mutation = session.get(Mutation, mutation.id)
            if not mutation:
                raise ValueError("Mutation not found")

            # Snapshot current active state as the base version
            base_version = self._create_harness_version(session)
            mutation.base_version_id = base_version.id

            if mutation.kind == MutationKind.prompt:
                old_target = self._resolve_prompt_target(session, mutation)
                self._apply_prompt_mutation(session, mutation)
                candidate_version = self._create_harness_version(
                    session,
                    prompt_override=(old_target.id if old_target else None, mutation.target_id),
                )
            elif mutation.kind == MutationKind.tool:
                old_target = self._resolve_tool_target(session, mutation)
                self._apply_tool_mutation(session, mutation)
                candidate_version = self._create_harness_version(
                    session,
                    tool_override=(old_target.id if old_target else None, mutation.target_id),
                )
            elif mutation.kind == MutationKind.strategy:
                old_target = self._resolve_strategy_target(session, mutation)
                self._apply_strategy_mutation(session, mutation)
                candidate_version = self._create_harness_version(
                    session,
                    strategy_override=(old_target.id if old_target else None, mutation.target_id),
                )

            mutation.candidate_version_id = candidate_version.id
            mutation.status = MutationStatus.candidate
            mutation.decided_ts = datetime.now(timezone.utc)

            session.commit()
            session.refresh(candidate_version)
            return candidate_version

    def promote_mutation(self, mutation: Mutation) -> HarnessVersion:
        """Promote a candidate mutation to active global state."""
        with get_session() as session:
            mutation = session.get(Mutation, mutation.id)
            if not mutation or mutation.status != MutationStatus.candidate:
                raise ValueError("Mutation not in candidate state")

            if mutation.kind == MutationKind.prompt:
                self._promote_prompt(session, mutation)
            elif mutation.kind == MutationKind.tool:
                self._promote_tool(session, mutation)
            elif mutation.kind == MutationKind.strategy:
                self._promote_strategy(session, mutation)

            mutation.status = MutationStatus.promoted
            mutation.decided_ts = datetime.now(timezone.utc)
            version = self._create_harness_version(session)
            session.commit()
            session.refresh(version)
            return version

    def rollback_mutation(self, mutation: Mutation) -> HarnessVersion:
        """Rollback a candidate mutation and restore previous active state."""
        with get_session() as session:
            mutation = session.get(Mutation, mutation.id)
            if not mutation:
                raise ValueError("Mutation not found")

            if mutation.kind == MutationKind.prompt:
                self._rollback_prompt(session, mutation)
            elif mutation.kind == MutationKind.tool:
                self._rollback_tool(session, mutation)
            elif mutation.kind == MutationKind.strategy:
                self._rollback_strategy(session, mutation)

            mutation.status = MutationStatus.rolled_back
            mutation.decided_ts = datetime.now(timezone.utc)
            version = self._create_harness_version(session)
            session.commit()
            session.refresh(version)
            return version

    # -- Prompt helpers --

    def _resolve_prompt_target(self, session, mutation: Mutation) -> Optional[Prompt]:
        if mutation.target_id:
            return session.query(Prompt).filter(Prompt.id == mutation.target_id).first()
        role_str = mutation.after.get("role") or mutation.before.get("role") or mutation.target_name
        if role_str:
            return session.query(Prompt).filter(
                Prompt.role == role_str,
                Prompt.status == PromptStatus.active,
            ).first()
        return None

    def _apply_prompt_mutation(self, session, mutation: Mutation):
        old_prompt = self._resolve_prompt_target(session, mutation)
        role = old_prompt.role if old_prompt else (mutation.after.get("role") or PromptRole.system)
        text = mutation.after.get("text", "")
        new_prompt = Prompt(
            role=role,
            version=self._next_version(old_prompt.version if old_prompt else "1.0.0"),
            text=text,
            status=PromptStatus.candidate,
            parent_id=old_prompt.id if old_prompt else None,
        )
        session.add(new_prompt)
        session.flush()
        mutation.target_id = new_prompt.id

    def _promote_prompt(self, session, mutation: Mutation):
        candidate = session.query(Prompt).filter(Prompt.id == mutation.target_id).first()
        if candidate and candidate.parent_id:
            parent = session.query(Prompt).filter(Prompt.id == candidate.parent_id).first()
            if parent:
                parent.status = PromptStatus.archived
        if candidate:
            candidate.status = PromptStatus.active

    def _rollback_prompt(self, session, mutation: Mutation):
        candidate = session.query(Prompt).filter(Prompt.id == mutation.target_id).first()
        if candidate:
            candidate.status = PromptStatus.archived
            if candidate.parent_id:
                parent = session.query(Prompt).filter(Prompt.id == candidate.parent_id).first()
                if parent:
                    parent.status = PromptStatus.active

    # -- Tool helpers --

    def _resolve_tool_target(self, session, mutation: Mutation) -> Optional[Tool]:
        if mutation.target_id:
            return session.query(Tool).filter(Tool.id == mutation.target_id).first()
        name = mutation.after.get("name") or mutation.before.get("name") or mutation.target_name
        if name:
            return session.query(Tool).filter(
                Tool.name == name,
                Tool.status == ToolStatus.active,
            ).first()
        return None

    def _apply_tool_mutation(self, session, mutation: Mutation):
        old_tool = self._resolve_tool_target(session, mutation)
        name = mutation.after.get("name") or (old_tool.name if old_tool else "dynamic_tool")
        new_tool = Tool(
            name=name,
            version=self._next_version(old_tool.version if old_tool else "1.0.0"),
            description=mutation.after.get("description", old_tool.description if old_tool else ""),
            json_schema=mutation.after.get("json_schema") or (old_tool.json_schema if old_tool else {}),
            implementation_kind=mutation.after.get("implementation_kind") or (old_tool.implementation_kind if old_tool else ToolKind.python_code),
            code=mutation.after.get("code", old_tool.code if old_tool else None),
            source_url=mutation.after.get("source_url", old_tool.source_url if old_tool else None),
            status=ToolStatus.candidate,
        )
        session.add(new_tool)
        session.flush()
        mutation.target_id = new_tool.id

    def _promote_tool(self, session, mutation: Mutation):
        candidate = session.query(Tool).filter(Tool.id == mutation.target_id).first()
        if not candidate:
            return
        # Find the parent (previous active tool with same name)
        parent = session.query(Tool).filter(
            Tool.name == candidate.name,
            Tool.id != candidate.id,
            Tool.status == ToolStatus.active,
        ).order_by(Tool.id.desc()).first()
        if parent:
            parent.status = ToolStatus.deprecated
        candidate.status = ToolStatus.active

    def _rollback_tool(self, session, mutation: Mutation):
        candidate = session.query(Tool).filter(Tool.id == mutation.target_id).first()
        if candidate:
            candidate.status = ToolStatus.deprecated

    # -- Strategy helpers --

    def _resolve_strategy_target(self, session, mutation: Mutation) -> Optional[Strategy]:
        if mutation.target_id:
            return session.query(Strategy).filter(Strategy.id == mutation.target_id).first()
        key = mutation.after.get("key") or mutation.before.get("key") or mutation.target_name
        if key:
            return session.query(Strategy).filter(
                Strategy.key == key,
                Strategy.status == StrategyStatus.active,
            ).first()
        return None

    def _apply_strategy_mutation(self, session, mutation: Mutation):
        old_strategy = self._resolve_strategy_target(session, mutation)
        key = mutation.after.get("key", old_strategy.key if old_strategy else "")
        new_strategy = Strategy(
            key=key,
            value=mutation.after.get("value", {}),
            version=self._next_version(old_strategy.version if old_strategy else "1.0.0"),
            status=StrategyStatus.candidate,
        )
        session.add(new_strategy)
        session.flush()
        mutation.target_id = new_strategy.id

    def _promote_strategy(self, session, mutation: Mutation):
        candidate = session.query(Strategy).filter(Strategy.id == mutation.target_id).first()
        if not candidate:
            return
        parent = session.query(Strategy).filter(
            Strategy.key == candidate.key,
            Strategy.id != candidate.id,
            Strategy.status == StrategyStatus.active,
        ).order_by(Strategy.id.desc()).first()
        if parent:
            parent.status = StrategyStatus.archived
        candidate.status = StrategyStatus.active

    def _rollback_strategy(self, session, mutation: Mutation):
        candidate = session.query(Strategy).filter(Strategy.id == mutation.target_id).first()
        if candidate:
            candidate.status = StrategyStatus.archived
            parent = session.query(Strategy).filter(
                Strategy.key == candidate.key,
                Strategy.id != candidate.id,
            ).order_by(Strategy.id.desc()).first()
            if parent:
                parent.status = StrategyStatus.active

    # -- Version snapshot --

    def _create_harness_version(
        self,
        session,
        prompt_override: Optional[tuple] = None,
        tool_override: Optional[tuple] = None,
        strategy_override: Optional[tuple] = None,
    ) -> HarnessVersion:
        active_prompts = session.query(Prompt).filter(
            Prompt.status == PromptStatus.active
        ).all()
        prompt_ids = [p.id for p in active_prompts]
        if prompt_override:
            old_id, new_id = prompt_override
            if old_id and old_id in prompt_ids:
                prompt_ids[prompt_ids.index(old_id)] = new_id
            elif new_id and new_id not in prompt_ids:
                prompt_ids.append(new_id)

        active_tools = session.query(Tool).filter(
            Tool.status == ToolStatus.active
        ).all()
        tool_ids = [t.id for t in active_tools]
        if tool_override:
            old_id, new_id = tool_override
            if old_id and old_id in tool_ids:
                tool_ids[tool_ids.index(old_id)] = new_id
            elif new_id and new_id not in tool_ids:
                tool_ids.append(new_id)

        active_strategies = session.query(Strategy).filter(
            Strategy.status == StrategyStatus.active
        ).all()
        strategy_ids = [s.id for s in active_strategies]
        if strategy_override:
            old_id, new_id = strategy_override
            if old_id and old_id in strategy_ids:
                strategy_ids[strategy_ids.index(old_id)] = new_id
            elif new_id and new_id not in strategy_ids:
                strategy_ids.append(new_id)

        version = HarnessVersion(
            label=f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            prompt_set=prompt_ids,
            tool_set=tool_ids,
            strategy_set=strategy_ids,
        )
        session.add(version)
        session.flush()
        return version

    @staticmethod
    def _next_version(version: str) -> str:
        """Bump semantic-ish versions without assuming they are floats."""
        parts = version.split(".")
        if parts and parts[-1].isdigit():
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        return f"{version}.1"

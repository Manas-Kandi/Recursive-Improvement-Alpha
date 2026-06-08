"""Propose, apply, and rollback mutations"""

from typing import Dict, Any, Optional
from siha.db import get_session
from siha.models import (
    Prompt, PromptStatus, Strategy, StrategyStatus,
    Mutation, MutationStatus, MutationKind, HarnessVersion
)
from datetime import datetime


class Mutator:
    """Manages mutation lifecycle: propose, apply, rollback"""
    
    def propose_mutation(self, mutation_data: Dict[str, Any]) -> Mutation:
        """Create a pending mutation from analysis results"""
        
        with get_session() as session:
            mutation = Mutation(
                kind=mutation_data["kind"],
                target_id=mutation_data.get("target_id", 0),
                before=mutation_data.get("before", {}),
                after=mutation_data.get("after", {}),
                rationale=mutation_data.get("rationale", ""),
                status=MutationStatus.pending
            )
            session.add(mutation)
            session.commit()
            session.refresh(mutation)
            return mutation
    
    def apply_mutation(self, mutation: Mutation) -> HarnessVersion:
        """Apply a mutation and create a new harness version"""
        
        with get_session() as session:
            # Create candidate versions based on mutation kind
            if mutation.kind == MutationKind.prompt:
                self._apply_prompt_mutation(session, mutation)
            elif mutation.kind == MutationKind.tool:
                self._apply_tool_mutation(session, mutation)
            elif mutation.kind == MutationKind.strategy:
                self._apply_strategy_mutation(session, mutation)
            
            # Update mutation status
            mutation.status = MutationStatus.active
            mutation.decided_ts = datetime.utcnow()
            
            # Create new harness version snapshot
            version = self._create_harness_version(session)
            
            session.commit()
            session.refresh(version)
            return version
    
    def _apply_prompt_mutation(self, session, mutation: Mutation):
        """Apply a prompt mutation"""
        # Deactivate old prompt
        old_prompt = session.query(Prompt).filter(
            Prompt.id == mutation.target_id
        ).first()
        if old_prompt:
            old_prompt.status = PromptStatus.archived
        
        # Create new candidate prompt
        new_prompt = Prompt(
            role=old_prompt.role if old_prompt else "system",
            version="2.0.0",
            text=mutation.after.get("text", ""),
            status=PromptStatus.active,
            parent_id=mutation.target_id
        )
        session.add(new_prompt)
        session.flush()
        mutation.target_id = new_prompt.id
    
    def _apply_tool_mutation(self, session, mutation: Mutation):
        """Apply a tool mutation"""
        from siha.models import Tool, ToolStatus
        
        # Update tool
        tool = session.query(Tool).filter(Tool.id == mutation.target_id).first()
        if tool:
            if "code" in mutation.after:
                tool.code = mutation.after["code"]
            if "description" in mutation.after:
                tool.description = mutation.after["description"]
            tool.version = str(float(tool.version) + 0.1)
    
    def _apply_strategy_mutation(self, session, mutation: Mutation):
        """Apply a strategy mutation"""
        # Update or create strategy
        strategy = session.query(Strategy).filter(
            Strategy.key == mutation.after.get("key", "")
        ).first()
        
        if strategy:
            strategy.status = StrategyStatus.archived
        
        new_strategy = Strategy(
            key=mutation.after.get("key", ""),
            value=mutation.after.get("value", {}),
            version="2.0.0",
            status=StrategyStatus.active
        )
        session.add(new_strategy)
        session.flush()
        mutation.target_id = new_strategy.id
    
    def _create_harness_version(self, session) -> HarnessVersion:
        """Create a snapshot of current harness state"""
        
        # Get active prompts
        active_prompts = session.query(Prompt).filter(
            Prompt.status == PromptStatus.active
        ).all()
        prompt_ids = [p.id for p in active_prompts]
        
        # Get active tools
        from siha.models import Tool, ToolStatus
        active_tools = session.query(Tool).filter(
            Tool.status == ToolStatus.active
        ).all()
        tool_ids = [t.id for t in active_tools]
        
        # Get active strategies
        active_strategies = session.query(Strategy).filter(
            Strategy.status == StrategyStatus.active
        ).all()
        strategy_ids = [s.id for s in active_strategies]
        
        version = HarnessVersion(
            label=f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            prompt_set=prompt_ids,
            tool_set=tool_ids,
            strategy_set=strategy_ids
        )
        session.add(version)
        session.flush()
        return version
    
    def rollback_mutation(self, mutation: Mutation) -> HarnessVersion:
        """Rollback a mutation to previous state"""
        
        with get_session() as session:
            mutation.status = MutationStatus.reverted
            mutation.decided_ts = datetime.utcnow()
            
            # Restore parent versions
            if mutation.kind == MutationKind.prompt:
                self._restore_prompt_parent(session, mutation)
            elif mutation.kind == MutationKind.strategy:
                self._restore_strategy_parent(session, mutation)
            
            # Create new version snapshot
            version = self._create_harness_version(session)
            session.commit()
            session.refresh(version)
            return version
    
    def _restore_prompt_parent(self, session, mutation: Mutation):
        """Restore parent prompt"""
        if mutation.target_id:
            prompt = session.query(Prompt).filter(Prompt.id == mutation.target_id).first()
            if prompt and prompt.parent_id:
                prompt.status = PromptStatus.archived
                parent = session.query(Prompt).filter(Prompt.id == prompt.parent_id).first()
                if parent:
                    parent.status = PromptStatus.active
    
    def _restore_strategy_parent(self, session, mutation: Mutation):
        """Restore parent strategy"""
        # Similar to prompt restoration
        pass

"""Prompt management - loads active versions from DB"""

from typing import Optional
from siha.db import get_session
from siha.models import Prompt, PromptRole
from sqlmodel import select

def get_active_prompt(role: PromptRole, harness_version_id: Optional[int] = None) -> Optional[str]:
    """Load the active prompt for a given role from the database.

    If ``harness_version_id`` is provided, load from that version's prompt set
    instead of globally active prompts.
    """
    from siha.models import HarnessVersion

    with get_session() as session:
        if harness_version_id is not None:
            version = session.get(HarnessVersion, harness_version_id)
            if version and version.prompt_set:
                prompt = session.exec(select(Prompt).where(
                    Prompt.role == role,
                    Prompt.id.in_(version.prompt_set),
                )).first()
                if prompt:
                    return prompt.text
        prompt = session.exec(select(Prompt).where(
            Prompt.role == role,
            Prompt.status == "active",
        )).first()
        return prompt.text if prompt else None


def seed_default_prompts():
    """Seed default prompts if none exist"""
    from siha.db import init_db
    
    init_db()
    
    default_prompts = [
        {
            "role": PromptRole.system,
            "text": "You are a helpful coding assistant. You can plan and execute code to solve user requests. Break down problems into steps, write clear code, and explain your reasoning."
        },
        {
            "role": PromptRole.planner,
            "text": "Plan the solution step by step. Identify what tools you need and what code to write."
        },
        {
            "role": PromptRole.recovery,
            "text": "Analyze the error and propose a fix. If the error is unclear, add logging to diagnose."
        },
        {
            "role": PromptRole.meta,
            "text": "Analyze the task execution trace. Identify what went well, what failed, and propose specific improvements to prompts, tools, or strategies."
        },
        {
            "role": PromptRole.discovery,
            "text": "Search for and synthesize a new tool implementation. Find a library or API that can solve the user's need, read its documentation, and write a safe Python wrapper."
        }
    ]
    
    with get_session() as session:
        for prompt_def in default_prompts:
            existing = session.exec(select(Prompt).where(
                Prompt.role == prompt_def["role"],
                Prompt.status == "active"
            )).first()
            
            if not existing:
                prompt = Prompt(
                    role=prompt_def["role"],
                    version="1.0.0",
                    text=prompt_def["text"],
                    status="active"
                )
                session.add(prompt)
        
        session.commit()

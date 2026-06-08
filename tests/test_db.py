"""Tests for database functionality"""

import pytest
from siha.db import init_db, get_session
from siha.models import Task, TaskStatus, Prompt, PromptRole


def test_database_initialization():
    """Test database table creation"""
    init_db()
    
    # Should not raise an error
    assert True


def test_task_creation():
    """Test creating a task"""
    init_db()
    
    with get_session() as session:
        task = Task(
            user_prompt="test prompt",
            model="test-model",
            status=TaskStatus.running,
            sandbox_mode="local"
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        
        assert task.id is not None
        assert task.user_prompt == "test prompt"


def test_prompt_creation():
    """Test creating a prompt"""
    init_db()
    
    with get_session() as session:
        prompt = Prompt(
            role=PromptRole.system,
            version="1.0.0",
            text="Test prompt",
            status="active"
        )
        session.add(prompt)
        session.commit()
        session.refresh(prompt)
        
        assert prompt.id is not None
        assert prompt.role == PromptRole.system

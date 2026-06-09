"""Task lifecycle and trace recording"""

from typing import Optional
from siha.models import Task
from siha.db import get_session


class Session:
    """Manages a single task session"""
    
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.task: Optional[Task] = None
        self._load_task()
    
    def _load_task(self):
        """Load task from database"""
        with get_session() as session:
            self.task = session.get(Task, self.task_id)
    
    def get_trace(self) -> dict:
        """Get full execution trace"""
        from siha.models import Step, ToolCall
        
        with get_session() as session:
            task = session.get(Task, self.task_id)
            steps = session.query(Step).filter(Step.task_id == self.task_id).order_by(Step.idx).all()
            tool_calls = session.query(ToolCall).filter(ToolCall.task_id == self.task_id).all()
            
            return {
                "task": {
                    "id": task.id,
                    "prompt": task.user_prompt,
                    "model": task.model,
                    "status": task.status,
                    "duration_ms": task.duration_ms,
                    "sandbox_mode": task.sandbox_mode,
                    "error_summary": task.error_summary,
                    "trace_id": task.trace_id,
                },
                "steps": [
                    {
                        "idx": s.idx,
                        "type": s.type,
                        "content": s.content,
                        "tokens": s.tokens,
                        "latency_ms": s.latency_ms
                    }
                    for s in steps
                ],
                "tool_calls": [
                    {
                        "id": tc.id,
                        "tool_id": tc.tool_id,
                        "args": tc.args,
                        "result": tc.result,
                        "success": tc.success,
                        "duration_ms": tc.duration_ms
                    }
                    for tc in tool_calls
                ]
            }

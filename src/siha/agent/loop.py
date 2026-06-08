"""ReAct agent loop: plan → act → observe"""

import json
import time
from typing import List, Dict, Any, Optional
from siha.llm.client import NvidiaClient
from siha.db import get_session
from siha.models import Task, Step, StepType, TaskStatus, ToolCall
from siha.tools.registry import ToolRegistry
from siha.sandbox import create_sandbox


class AgentLoop:
    """ReAct-style agent loop with tool calling"""

    def __init__(self, model: Optional[str] = None):
        self.client = NvidiaClient(model)
        self.step_count = 0
        self.task: Optional[Task] = None
        # Each loop gets its own registry so a per-task sandbox can be bound
        # without interfering with concurrent runs.
        self.registry = ToolRegistry()
        self.sandbox = None

    def run(self, user_prompt: str, sandbox_mode: str = "local") -> Task:
        """Run the agent loop for a user prompt"""
        from siha.config import settings

        start_time = time.time()
        self.step_count = 0

        # Create task record
        with get_session() as session:
            self.task = Task(
                user_prompt=user_prompt,
                model=self.client.model,
                status=TaskStatus.running,
                sandbox_mode=sandbox_mode,
            )
            session.add(self.task)
            session.commit()
            session.refresh(self.task)
            task_id = self.task.id

        # Bind a shared per-task sandbox to all tools.
        self.sandbox = create_sandbox(sandbox_mode)
        self.registry.set_sandbox(self.sandbox)

        # Build initial messages
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        tools = self.registry.to_openai_tools()

        final_answer: Optional[str] = None
        error_summary: Optional[str] = None
        status = TaskStatus.success

        try:
            while self.step_count < settings.step_budget:
                step_start = time.time()

                response = self.client.chat(messages, tools=tools)
                choice = response.choices[0]
                message = choice.message
                tokens = response.usage.total_tokens if response.usage else 0

                if message.tool_calls:
                    self._record_step(
                        StepType.tool_call,
                        {"tool_calls": [tc.model_dump() for tc in message.tool_calls]},
                        tokens,
                        int((time.time() - step_start) * 1000),
                    )

                    # Append the assistant message with ALL tool calls once.
                    messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [tc.model_dump() for tc in message.tool_calls],
                    })

                    # Then one tool response message per tool call.
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = self._parse_args(tool_call.function.arguments)

                        tool_result = self._execute_tool(tool_name, tool_args)
                        self._record_tool_call(tool_name, tool_args, tool_result)

                        content = tool_result.output or tool_result.error or ""
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": content[: settings.max_output_bytes],
                        })
                else:
                    self._record_step(
                        StepType.plan,
                        {"content": message.content},
                        tokens,
                        int((time.time() - step_start) * 1000),
                    )

                    if choice.finish_reason == "stop":
                        final_answer = message.content or ""
                        messages.append({"role": "assistant", "content": final_answer})
                        self._record_step(StepType.final, {"content": final_answer}, tokens, 0)
                        break

                self.step_count += 1
            else:
                # Loop exhausted the step budget without a final answer.
                status = TaskStatus.failed
                error_summary = f"Step budget ({settings.step_budget}) exhausted before completion."
        except Exception as e:
            status = TaskStatus.failed
            error_summary = str(e)
        finally:
            if self.sandbox is not None:
                try:
                    self.sandbox.cleanup()
                except Exception:
                    pass

        duration_ms = int((time.time() - start_time) * 1000)
        with get_session() as session:
            task = session.get(Task, task_id)
            task.status = status
            task.duration_ms = duration_ms
            task.final_answer = final_answer
            task.error_summary = error_summary
            session.commit()
            session.refresh(task)
            self.task = task

        return self.task

    @staticmethod
    def _parse_args(raw: str) -> Dict[str, Any]:
        """Safely parse tool-call arguments as JSON."""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_system_prompt(self) -> str:
        """Get the active system prompt from the DB, falling back to a default."""
        from siha.agent.prompts import get_active_prompt
        from siha.models import PromptRole

        prompt = get_active_prompt(PromptRole.system)
        if prompt:
            return prompt
        return (
            "You are a helpful coding assistant. You can plan and execute code to "
            "solve user requests. Break down problems into steps, write clear code, "
            "and explain your reasoning. When you have completed the task, provide a "
            "final answer without further tool calls."
        )
    
    def _record_step(self, step_type: StepType, content: Dict[str, Any], tokens: int, latency_ms: int):
        """Record a step to the database"""
        with get_session() as session:
            step = Step(
                task_id=self.task.id,
                idx=self.step_count,
                type=step_type,
                content=content,
                tokens=tokens,
                latency_ms=latency_ms
            )
            session.add(step)
            session.commit()
    
    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]):
        """Execute a tool by name"""
        try:
            tool = self.registry.get_tool(tool_name)
            return tool.run(**tool_args)
        except Exception as e:
            from siha.tools.base import ToolResult
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _record_tool_call(self, tool_name: str, tool_args: Dict[str, Any], tool_result):
        """Record a tool call to the database"""
        from siha.models import Tool as ToolModel
        
        with get_session() as session:
            # Get or create tool record
            tool = session.query(ToolModel).filter(ToolModel.name == tool_name).first()
            if not tool:
                tool = ToolModel(
                    name=tool_name,
                    version="1.0.0",
                    description="Builtin tool",
                    json_schema={},
                    implementation_kind="builtin"
                )
                session.add(tool)
                session.commit()
                session.refresh(tool)
            
            tool_call = ToolCall(
                task_id=self.task.id,
                tool_id=tool.id,
                args=tool_args,
                result={"output": tool_result.output, "error": tool_result.error, "data": tool_result.data},
                success=tool_result.success,
                duration_ms=0  # TODO: track actual duration
            )
            session.add(tool_call)
            session.commit()

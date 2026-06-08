"""ReAct agent loop: plan → act → observe"""

import json
import time
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional
from siha.llm.factory import create_llm_client
from siha.db import get_session
from siha.models import Task, Step, StepType, TaskStatus, TaskCategory, ToolCall
from siha.tools.registry import ToolRegistry
from siha.sandbox import create_sandbox
from siha.portal.events import event_bus


class AgentLoop:
    """ReAct-style agent loop with tool calling"""

    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        harness_version_id: Optional[int] = None,
    ):
        self.client = create_llm_client(model=model, provider=provider)
        self.step_count = 0
        self.task: Optional[Task] = None
        self.harness_version_id = harness_version_id
        # Each loop gets its own registry so a per-task sandbox can be bound
        # without interfering with concurrent runs.
        self.registry = ToolRegistry(harness_version_id=harness_version_id)
        self.sandbox = None

    def run(
        self,
        user_prompt: str,
        sandbox_mode: str = "local",
        workspace_dir: Optional[Path] = None,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        category: TaskCategory = TaskCategory.user,
        trace_id: Optional[str] = None,
    ) -> Task:
        """Run the agent loop for a user prompt."""
        from siha.config import settings
        from uuid import uuid4

        _emit = on_event if on_event is not None else (lambda _e, _d: None)

        start_time = time.time()
        self.step_count = 0
        resolved_trace_id = trace_id or str(uuid4())

        # Create task record
        with get_session() as session:
            self.task = Task(
                user_prompt=user_prompt,
                model=self.client.model,
                status=TaskStatus.running,
                sandbox_mode=sandbox_mode,
                harness_version_id=self.harness_version_id,
                category=category,
                trace_id=resolved_trace_id,
            )
            session.add(self.task)
            session.commit()
            session.refresh(self.task)
            task_id = self.task.id
        event_bus.publish("task_started", {"task_id": task_id, "prompt": user_prompt, "trace_id": resolved_trace_id})

        # Bind a shared per-task sandbox to all tools.
        self.sandbox = create_sandbox(sandbox_mode, workspace_dir=workspace_dir)
        self.registry.set_sandbox(self.sandbox)

        # Build initial messages — inject prior conversation turns for context
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self._get_system_prompt()}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        tools = self.registry.to_openai_tools()

        final_answer: Optional[str] = None
        error_summary: Optional[str] = None
        status = TaskStatus.success

        try:
            while self.step_count < settings.step_budget:
                step_start = time.time()
                _emit("thinking_start", {"step": self.step_count})

                # Stream the LLM response and accumulate tokens + tool calls.
                content_parts: List[str] = []
                reasoning_parts: List[str] = []
                tool_calls_acc: Dict[int, Dict[str, Any]] = {}
                finish_reason: Optional[str] = None
                total_tokens = 0

                for chunk in self.client.stream(messages, tools=tools):
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
                    delta = choice.delta

                    reasoning = self.client.extract_reasoning(chunk)
                    if reasoning:
                        reasoning_parts.append(reasoning)
                        _emit("reasoning_token", {"token": reasoning, "step": self.step_count})

                    if delta.content:
                        content_parts.append(delta.content)
                        _emit("content_token", {"token": delta.content, "step": self.step_count})

                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc_delta.id:
                                tool_calls_acc[idx]["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_acc[idx]["function"]["name"] += tc_delta.function.name
                                if tc_delta.function.arguments:
                                    tool_calls_acc[idx]["function"]["arguments"] += tc_delta.function.arguments

                    if hasattr(chunk, "usage") and chunk.usage:
                        total_tokens = chunk.usage.total_tokens or 0

                full_content = "".join(content_parts)
                tool_calls_list = [tool_calls_acc[i] for i in sorted(tool_calls_acc.keys())]

                if tool_calls_list:
                    self._record_step(
                        StepType.tool_call,
                        {"tool_calls": tool_calls_list},
                        total_tokens,
                        int((time.time() - step_start) * 1000),
                    )

                    messages.append({
                        "role": "assistant",
                        "content": full_content or "",
                        "tool_calls": tool_calls_list,
                    })

                    for tool_call in tool_calls_list:
                        tool_name = tool_call["function"]["name"]
                        tool_args = self._parse_args(tool_call["function"]["arguments"])
                        _emit("tool_called", {"tool": tool_name, "args": tool_args, "step": self.step_count})

                        tool_exec_start = time.time()
                        tool_result = self._execute_tool(tool_name, tool_args)
                        tool_duration_ms = int((time.time() - tool_exec_start) * 1000)
                        self._record_tool_call(tool_name, tool_args, tool_result, tool_duration_ms)

                        content = tool_result.output or tool_result.error or ""
                        self._record_step(
                            StepType.observation,
                            {
                                "tool": tool_name,
                                "success": tool_result.success,
                                "output": tool_result.output,
                                "error": tool_result.error,
                                "data": tool_result.data,
                            },
                            0,
                            tool_duration_ms,
                        )
                        event_bus.publish(
                            "tool_call",
                            {
                                "task_id": task_id,
                                "tool": tool_name,
                                "success": tool_result.success,
                                "duration_ms": tool_duration_ms,
                            },
                        )
                        _emit("tool_result", {
                            "tool": tool_name,
                            "success": tool_result.success,
                            "output": (tool_result.output or "")[:300],
                            "error": tool_result.error,
                            "duration_ms": tool_duration_ms,
                            "step": self.step_count,
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": content[: settings.max_output_bytes],
                        })
                else:
                    self._record_step(
                        StepType.plan,
                        {"content": full_content},
                        total_tokens,
                        int((time.time() - step_start) * 1000),
                    )

                    if finish_reason == "stop":
                        final_answer = full_content or ""
                        messages.append({"role": "assistant", "content": final_answer})
                        self._record_step(StepType.final, {"content": final_answer}, total_tokens, 0)
                        _emit("final_answer", {"content": final_answer})
                        break

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
        event_bus.publish(
            "task_finished",
            {
                "task_id": task_id,
                "status": status.value,
                "duration_ms": duration_ms,
                "error_summary": error_summary,
            },
        )

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

        prompt = get_active_prompt(PromptRole.system, harness_version_id=self.harness_version_id)
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
            self.step_count += 1
    
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
    
    def _record_tool_call(self, tool_name: str, tool_args: Dict[str, Any], tool_result, duration_ms: int = 0):
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
                duration_ms=duration_ms
            )
            session.add(tool_call)
            session.commit()

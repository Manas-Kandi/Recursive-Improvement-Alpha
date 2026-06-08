"""ReAct agent loop: plan → act → observe"""

import json
import re
import time
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional
from siha.llm.factory import create_llm_client
from siha.db import get_session
from siha.models import Task, Step, StepType, TaskStatus, TaskCategory, ToolCall
from siha.tools.registry import ToolRegistry
from siha.sandbox import create_sandbox
from siha.portal.events import event_bus
from siha.agent.router import IntentRouter
from siha.agent.planner import TaskPlanner
from siha.agent.action_mapper import ActionMapper


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
        self.working_memory: Dict[str, Any] = {}  # Tracks recent actions for context

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

        # --- Intent Routing ---
        # A lightweight model classifies the intent so small models can
        # reliably distinguish chat from tool-use without confusing the
        # main execution model.
        router = IntentRouter()
        intent = router.classify(user_prompt)
        _emit("intent_classified", {"intent": intent})
        event_bus.publish("intent_classified", {"task_id": task_id, "intent": intent})

        # For pure chat, skip the tool loop entirely and do a single response.
        if intent == "chat":
            return self._run_chat_mode(user_prompt, task_id, history, _emit, start_time)

        # Tool-using modes: bind sandbox and enter the ReAct loop.
        self.sandbox = create_sandbox(sandbox_mode, workspace_dir=workspace_dir)
        self.registry.set_sandbox(self.sandbox)

        tools = self.registry.to_openai_tools()

        # Build initial messages — inject prior conversation turns for context
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self._get_system_prompt(intent)}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        # --- Action Mapping + Planning ---
        # Try deterministic templates FIRST (no LLM). Compound requests
        # ("create folder X and write file Y") may yield multiple steps.
        mapper = ActionMapper()
        steps = mapper.map(user_prompt)
        source = "template"

        if not steps:
            # Fall back to LLM planner for novel requests
            planner = TaskPlanner(
                provider=self.client.__class__.__name__.lower().replace("client", "") or None,
                model=self.client.model,
            )
            step = planner.plan_first_step(user_prompt, tools)
            if step:
                steps = [step]
            source = "planned"

        # Execute every planned step in sequence
        for step in steps:
            tool_name = step["function"]["name"]
            tool_args = self._parse_args(step["function"]["arguments"])
            _emit("action_step", {"tool": tool_name, "args": tool_args, "source": source})

            exec_start = time.time()
            tool_result = self._execute_tool(tool_name, tool_args)
            tool_duration_ms = int((time.time() - exec_start) * 1000)
            self._record_tool_call(tool_name, tool_args, tool_result, tool_duration_ms)

            self._update_working_memory(tool_name, tool_args, tool_result)

            content = tool_result.output or tool_result.error or ""
            self._record_step(
                StepType.tool_call,
                {"tool_calls": [step], "source": source},
                0,
                tool_duration_ms,
            )
            self._record_step(
                StepType.observation,
                {"tool": tool_name, "success": tool_result.success,
                 "output": tool_result.output, "error": tool_result.error},
                0,
                tool_duration_ms,
            )
            _emit("tool_result", {
                "tool": tool_name, "success": tool_result.success,
                "output": (tool_result.output or "")[:300],
                "error": tool_result.error, "duration_ms": tool_duration_ms,
            })
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [step],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": step["id"],
                "content": content[:settings.max_output_bytes],
            })

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

                # Fallback for models that don't support native tool_calls (e.g. Qwen via Ollama)
                if not tool_calls_list:
                    content_tool = self._try_parse_content_tool_call(full_content)
                    if content_tool:
                        tool_calls_list = [content_tool]

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

    @staticmethod
    def _try_parse_content_tool_call(content: str) -> Optional[Dict[str, Any]]:
        """Extract a tool call from raw content for models without native function calling.

        Accepts both formats:
            {"tool": "TOOL_NAME", "arguments": {...}}
            {"name": "TOOL_NAME", "arguments": {...}}
        """
        if not content:
            return None
        # Scan for JSON objects that look like tool calls (contain "tool"/"name" + "arguments")
        for match in re.finditer(r'\{[\s\S]*?"(?:tool|name)"[\s\S]*?"arguments"[\s\S]*?\}', content):
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
            tool_name = data.get("tool") or data.get("name")
            arguments = data.get("arguments") or data.get("args") or data.get("parameters", {})
            if not tool_name or not isinstance(tool_name, str):
                continue
            return {
                "id": f"call-{tool_name}-0",
                "type": "function",
                "function": {"name": tool_name, "arguments": json.dumps(arguments)},
            }
        return None

    def _run_chat_mode(
        self,
        user_prompt: str,
        task_id: int,
        history: Optional[List[Dict[str, Any]]],
        _emit: Callable[[str, Dict[str, Any]], None],
        start_time: float,
    ) -> Task:
        """Fast path for pure chat: single LLM call, no tools, no loop."""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": "You are a helpful coding assistant."}
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        _emit("thinking_start", {"step": 0, "mode": "chat"})
        content_parts: List[str] = []
        for chunk in self.client.stream(messages):
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                content_parts.append(token)
                _emit("content_token", {"token": token, "step": 0})

        final_answer = "".join(content_parts)
        duration_ms = int((time.time() - start_time) * 1000)

        with get_session() as session:
            task = session.get(Task, task_id)
            task.status = TaskStatus.success
            task.duration_ms = duration_ms
            task.final_answer = final_answer
            session.commit()
            session.refresh(task)
            self.task = task

        event_bus.publish(
            "task_finished",
            {"task_id": task_id, "status": "success", "duration_ms": duration_ms},
        )
        _emit("final_answer", {"content": final_answer})
        return self.task

    def _get_system_prompt(self, intent: Optional[str] = None) -> str:
        """Get the active system prompt from the DB, falling back to a default."""
        from siha.agent.prompts import get_active_prompt
        from siha.models import PromptRole

        prompt = get_active_prompt(PromptRole.system, harness_version_id=self.harness_version_id)
        if prompt:
            return prompt

        tool_list = []
        for name, tool in self.registry.tools.items():
            tool_list.append(f"- {name}: {tool.description}")

        # Tailor the prompt slightly based on classified intent
        intent_guidance = ""
        if intent == "code_generation":
            intent_guidance = (
                "The user wants you to WRITE code. Use write_file to create the "
                "files, then use run_shell or run_python to verify they work.\n"
            )
        elif intent == "analysis":
            intent_guidance = (
                "The user wants you to ANALYZE something. Use read_file to inspect "
                "code, then explain your findings.\n"
            )

        context = self._build_working_memory_context()

        return (
            "You are a helpful coding assistant with access to tools.\n\n"
            + intent_guidance
            + "RULES:\n"
            "1. When the user asks you to DO something, you MUST use the appropriate tool.\n"
            "   Do NOT explain how to do it — actually DO it via a tool call.\n"
            "2. When a tool IS needed, output EXACTLY one JSON object and nothing else:\n"
            '   {"tool": "TOOL_NAME", "arguments": {"arg1": "value1"}}\n'
            "3. After receiving a tool result, continue the task or give a final answer.\n\n"
            "EXAMPLE:\n"
            'User: "Create a file hello.txt with Hello World inside"\n'
            'WRONG: "Here is how you can create the file..."  (do NOT do this)\n'
            'RIGHT: {"tool": "write_file", "arguments": {"path": "hello.txt", "content": "Hello World"}}\n'
            "Then wait for the tool result and confirm completion.\n\n"
            + (context + "\n\n" if context else "")
            + "Available tools:\n"
            + "\n".join(tool_list)
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

    def _update_working_memory(self, tool_name: str, tool_args: Dict[str, Any], tool_result) -> None:
        """Track recent actions so follow-up requests have context."""
        if tool_name == "run_shell":
            cmd = tool_args.get("command", "")
            # Track directory creation
            if cmd.startswith("mkdir"):
                parts = cmd.split()
                if len(parts) >= 2:
                    self.working_memory["last_created_folder"] = parts[-1]
            # Track file moves
            elif cmd.startswith("mv"):
                parts = cmd.split()
                if len(parts) >= 3:
                    self.working_memory["last_moved_src"] = parts[1]
                    self.working_memory["last_moved_dst"] = parts[2]
        elif tool_name == "write_file":
            self.working_memory["last_written_file"] = tool_args.get("path", "")
        elif tool_name == "read_file":
            self.working_memory["last_read_file"] = tool_args.get("path", "")

    def _build_working_memory_context(self) -> str:
        """Format working memory into a context string for the system prompt."""
        if not self.working_memory:
            return ""
        lines = ["\nRecent context:"]
        if "last_created_folder" in self.working_memory:
            lines.append(f'- Created folder: "{self.working_memory["last_created_folder"]}"')
        if "last_written_file" in self.working_memory:
            lines.append(f'- Created file: "{self.working_memory["last_written_file"]}"')
        if "last_read_file" in self.working_memory:
            lines.append(f'- Read file: "{self.working_memory["last_read_file"]}"')
        return "\n".join(lines)

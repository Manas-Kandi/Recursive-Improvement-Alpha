"""Pydantic schemas for API responses and analyzer outputs."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel


# -- Analyzer schemas --

class ProposedMutation(BaseModel):
    """A mutation proposed by the analyzer."""
    kind: str
    target: str
    before: Optional[Any] = None
    after: Optional[Any] = None
    rationale: str
    expected_effect: Optional[str] = None


class Critique(BaseModel):
    """Structured critique output from the analyzer."""
    root_cause: str
    what_went_well: List[str]
    proposed_mutations: List[ProposedMutation]


# -- Session schemas --

class SessionListItem(BaseModel):
    """Summary of a session/task for list views."""
    id: int
    prompt: str
    model: str
    status: str
    duration_ms: Optional[int]
    ts: str
    category: str
    trace_id: Optional[str]


class StepDetail(BaseModel):
    """A single step in a session trace."""
    id: int
    idx: int
    type: str
    content: Dict[str, Any]
    tokens: Optional[int]
    latency_ms: Optional[int]


class ToolCallDetail(BaseModel):
    """A tool call recorded during a session."""
    id: int
    tool_id: int
    args: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    success: bool
    duration_ms: Optional[int]


class TaskDetail(BaseModel):
    """Full task metadata."""
    id: int
    prompt: str
    model: str
    status: str
    duration_ms: Optional[int]
    sandbox_mode: str
    error_summary: Optional[str]
    ts: str
    category: str
    trace_id: Optional[str]


class SessionDetail(BaseModel):
    """Full session detail including steps and tool calls."""
    task: TaskDetail
    steps: List[StepDetail]
    tool_calls: List[ToolCallDetail]


# -- Harness schemas --

class PromptState(BaseModel):
    """An active prompt."""
    id: int
    role: str
    version: str
    text: str


class ToolState(BaseModel):
    """An active tool."""
    id: int
    name: str
    version: str
    description: str


class StrategyState(BaseModel):
    """An active strategy."""
    id: int
    key: str
    value: Any
    version: str


class HarnessState(BaseModel):
    """Current harness state snapshot."""
    prompts: List[PromptState]
    tools: List[ToolState]
    strategies: List[StrategyState]


class HarnessVersionItem(BaseModel):
    """A harness version summary."""
    id: int
    label: str
    ts: str
    prompt_count: int
    tool_count: int
    strategy_count: int


class VersionDiff(BaseModel):
    """Diff between two harness versions."""
    id: int
    label: str
    prompts: List[int]
    tools: List[int]
    strategies: List[int]


class VersionDiffResponse(BaseModel):
    """Response for version diff endpoint."""
    version_a: VersionDiff
    version_b: VersionDiff


# -- Mutation schemas --

class MutationItem(BaseModel):
    """A mutation record."""
    id: int
    kind: str
    target_id: Optional[int]
    before: Optional[Any]
    after: Optional[Any]
    rationale: Optional[str]
    status: str
    benchmark_delta: Optional[float]
    created_ts: str
    decided_ts: Optional[str]


class MutationActionResponse(BaseModel):
    """Response after approving or rejecting a mutation."""
    status: str


# -- Benchmark schemas --

class BenchmarkItem(BaseModel):
    """A benchmark definition."""
    id: int
    name: str
    category: str
    origin: str
    created_ts: str


class BenchmarkTrendPoint(BaseModel):
    """A single point in the benchmark trend."""
    version_id: int
    label: str
    score: float
    timestamp: str


class BenchmarkTrend(BaseModel):
    """Benchmark score trend across harness versions."""
    trend: List[BenchmarkTrendPoint]
    total_versions: int


class BenchmarkRunResult(BaseModel):
    """Result of running a single benchmark."""
    name: str
    score: float
    passed: bool


class BenchmarkRunAllResponse(BaseModel):
    """Response after running all benchmarks."""
    results: List[BenchmarkRunResult]


# -- Tool schemas --

class ToolItem(BaseModel):
    """A tool record."""
    id: int
    name: str
    version: str
    description: str
    status: str
    implementation_kind: str
    source_url: Optional[str]
    created_ts: str


# -- Task run schemas --

class RunTaskPayload(BaseModel):
    """Payload for the run task endpoint."""
    prompt: str
    sandbox: Optional[str] = None
    model: Optional[str] = None
    harness_version_id: Optional[int] = None
    trace_id: Optional[str] = None


class RunTaskResponse(BaseModel):
    """Response after running a task."""
    id: int
    status: str
    duration_ms: Optional[int]
    final_answer: Optional[str]
    error_summary: Optional[str]
    trace_id: Optional[str]


# -- Improvement schemas --

class ImprovementTriggerResponse(BaseModel):
    """Response after triggering improvement."""
    status: str

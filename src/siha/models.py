"""SQLModel database models"""

from sqlmodel import SQLModel, Field, Relationship, JSON, Column
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum


class TaskStatus(str, Enum):
    running = "running"
    success = "success"
    failed = "failed"


class TaskCategory(str, Enum):
    user = "user"
    benchmark = "benchmark"
    system = "system"


class StepType(str, Enum):
    plan = "plan"
    tool_call = "tool_call"
    observation = "observation"
    final = "final"


class ToolKind(str, Enum):
    builtin = "builtin"
    python_code = "python_code"


class ToolStatus(str, Enum):
    active = "active"
    candidate = "candidate"
    archived = "archived"


class PromptRole(str, Enum):
    system = "system"
    planner = "planner"
    recovery = "recovery"
    meta = "meta"
    discovery = "discovery"


class PromptStatus(str, Enum):
    active = "active"
    candidate = "candidate"
    archived = "archived"


class StrategyStatus(str, Enum):
    active = "active"
    candidate = "candidate"
    archived = "archived"


class MutationKind(str, Enum):
    prompt = "prompt"
    tool = "tool"
    strategy = "strategy"
    template = "template"


class TemplateStatus(str, Enum):
    active = "active"
    candidate = "candidate"
    archived = "archived"


class TemplateOrigin(str, Enum):
    seed = "seed"
    synthesized = "synthesized"
    manual = "manual"


class MutationStatus(str, Enum):
    proposed = "proposed"
    pending = "pending"
    candidate = "candidate"
    evaluating = "evaluating"
    promoted = "promoted"
    active = "active"
    reverted = "reverted"
    rejected = "rejected"
    rolled_back = "rolled_back"


class BenchmarkOrigin(str, Enum):
    seed = "seed"
    auto = "auto"


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_prompt: str = Field(index=True)
    model: str
    status: TaskStatus = Field(default=TaskStatus.running)
    duration_ms: Optional[int] = None
    sandbox_mode: str = "local"
    error_summary: Optional[str] = None
    final_answer: Optional[str] = None
    analyzed: bool = Field(default=False)
    harness_version_id: Optional[int] = Field(default=None)
    category: TaskCategory = Field(default=TaskCategory.user)
    trace_id: Optional[str] = Field(default=None, index=True)
    # Triage critique recorded by the improvement cycle (root cause,
    # failure categories, proposed mutation ids) — powers failure analytics.
    triage: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    steps: List["Step"] = Relationship(back_populates="task")
    tool_calls: List["ToolCall"] = Relationship(back_populates="task")


class Step(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id")
    idx: int
    type: StepType
    content: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    
    task: Task = Relationship(back_populates="steps")


class Tool(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    version: str = "1.0.0"
    description: str
    json_schema: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    implementation_kind: ToolKind
    code: Optional[str] = None
    source_url: Optional[str] = None
    status: ToolStatus = ToolStatus.active
    created_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolCall(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id")
    tool_id: int = Field(foreign_key="tool.id")
    args: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    result: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    success: bool = False
    duration_ms: Optional[int] = None
    
    task: Task = Relationship(back_populates="tool_calls")


class Prompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    role: PromptRole
    version: str
    text: str
    status: PromptStatus = PromptStatus.active
    parent_id: Optional[int] = None
    created_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Strategy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    version: str
    status: StrategyStatus = StrategyStatus.active
    created_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: MutationKind
    target_id: int = 0
    target_name: Optional[str] = Field(default=None)
    before: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    after: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    rationale: str
    status: MutationStatus = MutationStatus.proposed
    benchmark_delta: Optional[float] = None
    base_version_id: Optional[int] = Field(default=None)
    candidate_version_id: Optional[int] = Field(default=None)
    created_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_ts: Optional[datetime] = None


class Benchmark(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    category: str
    task_spec: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    assertion: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    origin: BenchmarkOrigin = BenchmarkOrigin.seed
    created_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    runs: List["BenchmarkRun"] = Relationship(back_populates="benchmark")


class BenchmarkRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    benchmark_id: int = Field(foreign_key="benchmark.id")
    harness_version: int = Field(foreign_key="harnessversion.id")
    passed: bool
    score: float
    duration_ms: int
    output: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    benchmark: Benchmark = Relationship(back_populates="runs")


class HarnessVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    label: str
    prompt_set: List[int] = Field(default_factory=list, sa_column=Column(JSON))
    tool_set: List[int] = Field(default_factory=list, sa_column=Column(JSON))
    strategy_set: List[int] = Field(default_factory=list, sa_column=Column(JSON))
    template_set: List[int] = Field(default_factory=list, sa_column=Column(JSON))


class ActionTemplate(SQLModel, table=True):
    """A learnable deterministic mapping from a user-utterance pattern to a tool call.

    ``args_template`` values may contain ``{1}``, ``{2}``, ... placeholders that
    are substituted with the corresponding regex capture groups at match time.
    Lower ``priority`` numbers are tried first.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    pattern: str
    tool_name: str
    args_template: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    priority: int = 100
    example: Optional[str] = None
    status: TemplateStatus = TemplateStatus.active
    origin: TemplateOrigin = TemplateOrigin.seed
    version: str = "1.0.0"
    parent_id: Optional[int] = None
    source_task_id: Optional[int] = Field(default=None)
    hit_count: int = Field(default=0)
    # Graduated trust: synthesized templates are on probation until they
    # accumulate enough confirmed successes; repeated failures auto-archive.
    success_count: int = Field(default=0)
    failure_count: int = Field(default=0)
    created_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

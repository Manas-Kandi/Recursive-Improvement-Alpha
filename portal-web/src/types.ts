/** Core domain types shared across the frontend. */

export interface SessionItem {
  id: number
  prompt: string
  model: string
  status: string
  duration_ms: number | null
  ts: string
}

export interface StepDetail {
  id: number
  idx: number
  type: string
  content: Record<string, unknown>
  tokens: number | null
  latency_ms: number | null
}

export interface ToolCallDetail {
  id: number
  tool_id: number
  args: Record<string, unknown>
  result: Record<string, unknown> | null
  success: boolean
  duration_ms: number | null
}

export interface TaskDetail {
  id: number
  prompt: string
  model: string
  status: string
  duration_ms: number | null
  sandbox_mode: string
  error_summary: string | null
  ts: string
}

export interface SessionDetail {
  task: TaskDetail
  steps: StepDetail[]
  tool_calls: ToolCallDetail[]
}

export interface PromptState {
  id: number
  role: string
  version: string
  text: string
}

export interface ToolState {
  id: number
  name: string
  version: string
  description: string
}

export interface StrategyState {
  id: number
  key: string
  value: unknown
  version: string
}

export interface HarnessState {
  prompts: PromptState[]
  tools: ToolState[]
  strategies: StrategyState[]
}

export interface HarnessVersionItem {
  id: number
  label: string
  ts: string
  prompt_count: number
  tool_count: number
  strategy_count: number
}

export interface VersionDiff {
  id: number
  label: string
  prompts: number[]
  tools: number[]
  strategies: number[]
}

export interface VersionDiffResponse {
  version_a: VersionDiff
  version_b: VersionDiff
}

export interface MutationItem {
  id: number
  kind: string
  target_id: number | null
  before: unknown
  after: unknown
  rationale: string | null
  status: string
  benchmark_delta: number | null
  created_ts: string
  decided_ts: string | null
}

export interface MutationActionResponse {
  status: string
}

export interface BenchmarkItem {
  id: number
  name: string
  category: string
  origin: string
  created_ts: string
}

export interface BenchmarkTrendPoint {
  version_id: number
  label: string
  score: number
  timestamp: string
}

export interface BenchmarkTrend {
  trend: BenchmarkTrendPoint[]
  total_versions: number
}

export interface BenchmarkRunResult {
  name: string
  score: number
  passed: boolean
}

export interface BenchmarkRunAllResponse {
  results: BenchmarkRunResult[]
}

export interface ToolItem {
  id: number
  name: string
  version: string
  description: string
  status: string
  implementation_kind: string
  source_url: string | null
  created_ts: string
}

export interface RunTaskPayload {
  prompt: string
  sandbox?: string
  model?: string
  harness_version_id?: number
}

export interface RunTaskResponse {
  id: number
  status: string
  duration_ms: number | null
  final_answer: string | null
  error_summary: string | null
}

export interface ImprovementTriggerResponse {
  status: string
}

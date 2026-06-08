import axios, { AxiosResponse } from 'axios'
import type {
  SessionItem,
  SessionDetail,
  HarnessState,
  HarnessVersionItem,
  VersionDiffResponse,
  MutationItem,
  MutationActionResponse,
  BenchmarkItem,
  BenchmarkTrend,
  BenchmarkRunAllResponse,
  ToolItem,
  RunTaskPayload,
  RunTaskResponse,
  ImprovementTriggerResponse,
} from './types'

const API_BASE = '/api'
const AUTH_TOKEN = localStorage.getItem('siha_token') || 'dev'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Authorization': `Bearer ${AUTH_TOKEN}`
  }
})

export const apiClient = {
  getSessions: (): Promise<AxiosResponse<SessionItem[]>> =>
    api.get('/sessions'),

  getSession: (id: number): Promise<AxiosResponse<SessionDetail>> =>
    api.get(`/sessions/${id}`),

  getHarnessState: (): Promise<AxiosResponse<HarnessState>> =>
    api.get('/harness/state'),

  getHarnessVersions: (): Promise<AxiosResponse<HarnessVersionItem[]>> =>
    api.get('/harness/versions'),

  diffVersions: (a: number, b: number): Promise<AxiosResponse<VersionDiffResponse>> =>
    api.get(`/harness/versions/${a}/diff/${b}`),

  getMutations: (): Promise<AxiosResponse<MutationItem[]>> =>
    api.get('/mutations'),

  approveMutation: (id: number): Promise<AxiosResponse<MutationActionResponse>> =>
    api.post(`/mutations/${id}/approve`),

  rejectMutation: (id: number): Promise<AxiosResponse<MutationActionResponse>> =>
    api.post(`/mutations/${id}/reject`),

  getBenchmarks: (): Promise<AxiosResponse<BenchmarkItem[]>> =>
    api.get('/benchmarks'),

  getBenchmarkTrend: (): Promise<AxiosResponse<BenchmarkTrend>> =>
    api.get('/benchmarks/trend'),

  runAllBenchmarks: (): Promise<AxiosResponse<BenchmarkRunAllResponse>> =>
    api.post('/benchmarks/run-all'),

  getTools: (): Promise<AxiosResponse<ToolItem[]>> =>
    api.get('/tools'),

  runTask: (payload: RunTaskPayload): Promise<AxiosResponse<RunTaskResponse>> =>
    api.post('/run', payload),

  triggerImprovement: (): Promise<AxiosResponse<ImprovementTriggerResponse>> =>
    api.post('/improve'),
}

import axios from 'axios'

const API_BASE = '/api'
const AUTH_TOKEN = localStorage.getItem('siha_token') || 'dev'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Authorization': `Bearer ${AUTH_TOKEN}`
  }
})

export const apiClient = {
  getSessions: () => api.get('/sessions'),
  getSession: (id: number) => api.get(`/sessions/${id}`),
  getHarnessState: () => api.get('/harness/state'),
  getHarnessVersions: () => api.get('/harness/versions'),
  diffVersions: (a: number, b: number) => api.get(`/harness/versions/${a}/diff/${b}`),
  getMutations: () => api.get('/mutations'),
  approveMutation: (id: number) => api.post(`/mutations/${id}/approve`),
  rejectMutation: (id: number) => api.post(`/mutations/${id}/reject`),
  getBenchmarks: () => api.get('/benchmarks'),
  getBenchmarkTrend: () => api.get('/benchmarks/trend'),
  getTools: () => api.get('/tools'),
}

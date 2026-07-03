import axios from 'axios'

function getBaseURL() {
  return localStorage.getItem('vguard_server') || ''
}

import type {
  AppConfig,
  CandidateGenConfig,
  CandidateGenResult,
  DistributionData,
  HeatmapData,
  InjectionConfig,
  InjectionTaskStatus,
  SensitivityData,
  VerificationConfig,
  VerificationResult,
  VerificationTaskStatus,
} from '@/types'

const http = axios.create({
  baseURL: '',
  timeout: 300000,
})

http.interceptors.request.use(config => {
  const server = getBaseURL()
  if (server && config.url && !config.url.startsWith('http')) {
    config.baseURL = server
  }
  return config
})

// ============================================================
// Config
// ============================================================
export async function fetchConfig(): Promise<AppConfig> {
  const { data } = await http.get('/api/v1/config')
  return data
}

export async function fetchHealth(): Promise<{ status: string; mockMode: boolean; gpuAvailable: boolean }> {
  const { data } = await http.get('/api/v1/health')
  return data
}

// ============================================================
// Injection
// ============================================================
export async function startInjection(config: InjectionConfig): Promise<{ taskId: string }> {
  const { data } = await http.post('/api/v1/injection/start', config)
  return data
}

export async function getInjectionStatus(taskId: string): Promise<InjectionTaskStatus> {
  const { data } = await http.get(`/api/v1/injection/status/${taskId}`)
  return data
}

export async function cancelInjection(taskId: string): Promise<void> {
  await http.post(`/api/v1/injection/cancel/${taskId}`)
}

// ============================================================
// Verification
// ============================================================
export async function startVerification(config: VerificationConfig): Promise<{ taskId: string }> {
  const { data } = await http.post('/api/v1/verification/start', config)
  return data
}

export async function getVerificationStatus(taskId: string): Promise<VerificationTaskStatus> {
  const { data } = await http.get(`/api/v1/verification/status/${taskId}`)
  return data
}

export async function getVerificationResult(taskId: string): Promise<VerificationResult> {
  const { data } = await http.get(`/api/v1/verification/result/${taskId}`)
  return data
}

// ============================================================
// Candidates
// ============================================================
export async function generateCandidates(config: CandidateGenConfig): Promise<CandidateGenResult> {
  const { data } = await http.post('/api/v1/candidates/generate', config)
  return data
}

// ============================================================
// Mock Data (for charts)
// ============================================================
export async function fetchDistribution(feature: string): Promise<DistributionData> {
  const { data } = await http.get(`/api/v1/mock/distribution/${feature}`)
  return data
}

export async function fetchSensitivity(feature: string): Promise<SensitivityData> {
  const { data } = await http.get(`/api/v1/mock/sensitivity/${feature}`)
  return data
}

export async function fetchHeatmap(feature: string): Promise<HeatmapData> {
  const { data } = await http.get(`/api/v1/mock/heatmap/${feature}`)
  return data
}

// ============================================================
// WebSocket Connection Helpers
// ============================================================

export function createInjectionWs(taskId: string): WebSocket {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${protocol}//${location.host}/ws/injection/${taskId}`)
}

export function createVerificationWs(taskId: string): WebSocket {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${protocol}//${location.host}/ws/verification/${taskId}`)
}

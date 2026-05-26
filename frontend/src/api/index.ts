import axios, { type AxiosProgressEvent, type AxiosError } from 'axios'
import { reactive } from 'vue'

// ---- Axios 实例 ----

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// ---- 全局请求追踪（用于导航守卫） ----

export const requestTracker = reactive({
  pendingCount: 0,
})

api.interceptors.request.use((config) => {
  requestTracker.pendingCount++
  return config
})

api.interceptors.response.use(
  (response) => {
    requestTracker.pendingCount = Math.max(0, requestTracker.pendingCount - 1)
    return response
  },
  (error) => {
    requestTracker.pendingCount = Math.max(0, requestTracker.pendingCount - 1)
    return Promise.reject(error)
  },
)

// ---- 请求重试（仅 GET 请求，网络错误） ----

const MAX_RETRIES = 3
const RETRY_DELAY_MS = 1000

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config
  if (!config) return Promise.reject(error)

  // 只重试 GET 请求，且仅对网络/超时错误重试
  if (config.method?.toLowerCase() !== 'get') return Promise.reject(error)
  if (error.response) return Promise.reject(error) // 服务端有响应，不重试

  const retryCount = ((config as unknown) as Record<string, unknown>).__retryCount as number || 0
  if (retryCount >= MAX_RETRIES) return Promise.reject(error);

  ((config as unknown) as Record<string, unknown>).__retryCount = retryCount + 1
  await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS * Math.pow(2, retryCount)))
  return api(config)
})

// ---- 类型定义 ----

export interface SystemConfig {
  chunk_size: number
  chunk_overlap: number
  chunk_strategy: string
  semantic_breakpoint_type: string
  semantic_breakpoint_amount: number
  semantic_min_chunk_size: number
  embedding_model: string
  embedding_dimension: number | null
  reranker_model: string
  use_reranker: boolean
  default_model: string
  max_tokens: number
  temperature: number
  top_k: number
  reranker_top_n: number
  vector_db_path: string
  documents_path: string
  supported_document_extensions: string[]
}

export interface SystemConfigRequest {
  chunk_size?: number
  chunk_overlap?: number
  chunk_strategy?: string
  semantic_breakpoint_type?: string
  semantic_breakpoint_amount?: number
  semantic_min_chunk_size?: number
  embedding_model?: string
  reranker_model?: string
  use_reranker?: boolean
}

export interface QueryParams {
  question: string
  model: string
  temperature: number
  max_tokens: number
  top_k: number
  use_reranker: boolean
  reranker_top_n: number
  session_id: string
}

export interface StreamingQueryParams {
  question: string
  model: string
  temperature: number
  max_tokens: number
  top_k: number
  use_reranker: boolean
  reranker_top_n: number
  session_id: string
}

// ---- API 方法 ----

export default {
  healthCheck: () => api.get('/health'),
  preloadModels: () => api.get('/preload'),
  preloadModelRuntime: (data: { model: string; use_reranker: boolean }) =>
    api.post('/preload', data, { timeout: 600000 }),
  getPreloadStatus: (model: string) =>
    api.get('/preload/status', { params: { model } }),
  getModels: () => api.get('/models'),
  getConfig: () => api.get('/config'),
  updateConfig: (data: { model: string; api_key: string; secret_key?: string }) => api.post('/config', data),
  getApiKeyStatus: () =>
    api.get('/config/keys'),

  listDocuments: () => api.get('/documents'),
  uploadDocument: (file: File, onProgress?: (progressEvent: AxiosProgressEvent) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    })
  },
  deleteDocument: (filename: string) =>
    api.delete(`/documents/${encodeURIComponent(filename)}`),
  previewDocument: (filename: string) =>
    api.get(`/documents/preview/${encodeURIComponent(filename)}`),
  buildVectorStore: () => api.post('/vectorstore/build'),
  getBuildStatus: () => api.get('/vectorstore/build/status'),
  getVectorStoreStatus: () => api.get('/vectorstore/status'),
  query: (data: QueryParams) =>
    api.post('/query', data, { timeout: 600000 }),

  // 流式查询 (POST)
  queryStreamPost: async (data: StreamingQueryParams, signal?: AbortSignal) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const res = await fetch('/api/query/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
      signal,
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${res.status}: ${res.statusText}`)
    }
    return res
  },

  // 对话历史 API
  createSession: (title?: string) =>
    api.post('/chat/sessions', title ? { title } : {}),
  listSessions: () => api.get('/chat/sessions'),
  getSession: (sessionId: string) =>
    api.get(`/chat/sessions/${sessionId}`),
  updateSessionTitle: (sessionId: string, title: string) =>
    api.put(`/chat/sessions/${sessionId}/title`, { title }),
  deleteSession: (sessionId: string) =>
    api.delete(`/chat/sessions/${sessionId}`),
  clearAllSessions: () => api.delete('/chat/sessions'),

  // 系统配置 API
  getSystemConfig: () => api.get('/config/system'),
  updateSystemConfig: (data: SystemConfigRequest) => api.post('/config/system', data),

  // RAG 管道 API
  getPipelineStages: () => api.get('/pipeline/stages'),
  getIndexingStatus: () => api.get('/pipeline/indexing/status'),
  listChunks: (params?: { source?: string; limit?: number; offset?: number }) =>
    api.get('/pipeline/chunks', { params }),
  getChunkDetail: (chunkId: string) => api.get(`/pipeline/chunks/${encodeURIComponent(chunkId)}`),
  listSources: () => api.get('/pipeline/sources'),

  // 离线索引预览 API
  getIngestionPreview: () => api.get('/pipeline/ingestion/preview'),

  // 在线查询预览 API
  getQueryPreview: () => api.get('/pipeline/query/preview'),
}

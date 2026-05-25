import axios, { type AxiosProgressEvent, type AxiosError } from 'axios'

// ---- Token 管理 ----

const TOKEN_KEY = 'rag-auth-token'
const TOKEN_EXPIRY_KEY = 'rag-auth-token-expiry'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  // 解析 JWT payload 获取过期时间
  try {
    const parts = token.split('.')
    if (parts.length === 3) {
      const payload = JSON.parse(atob(parts[1]))
      if (payload.exp) {
        localStorage.setItem(TOKEN_EXPIRY_KEY, String(payload.exp * 1000))
        return
      }
    }
  } catch {
    // 解析失败，不存储过期时间
  }
  localStorage.removeItem(TOKEN_EXPIRY_KEY)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(TOKEN_EXPIRY_KEY)
}

export function isAuthenticated(): boolean {
  const token = getToken()
  if (!token) return false
  // 检查 token 是否过期
  const expiryStr = localStorage.getItem(TOKEN_EXPIRY_KEY)
  if (expiryStr) {
    const expiry = Number(expiryStr)
    if (!isNaN(expiry) && Date.now() >= expiry) {
      clearToken()
      return false
    }
  }
  return true
}

// 命名导出 verifyAuth，供路由守卫等服务端验证场景使用
export async function verifyAuth(): Promise<void> {
  await api.get('/auth/verify')
}

// ---- Axios 实例 ----

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 请求拦截器：自动附带 JWT Token
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 自动跳转登录页
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearToken()
      // 不在此处直接跳转，由 router guard 统一处理
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    }
    return Promise.reject(error)
  }
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
  embedding_model: string
  embedding_dimension: number | null
  reranker_model: string
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
  embedding_model?: string
  reranker_model?: string
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
  // 认证
  login: (password: string) =>
    api.post('/auth/login', { password }),
  verifyAuth: () => api.get('/auth/verify'),

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
    const token = getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const res = await fetch('/api/query/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
      signal,
    })
    if (!res.ok) {
      if (res.status === 401) {
        clearToken()
        window.dispatchEvent(new CustomEvent('auth:unauthorized'))
      }
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
}
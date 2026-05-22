/** 检索结果文档 */
export interface RetrievalDoc {
  index: number
  source: string
  score?: number
  content_preview?: string
  content?: string
}

/** 聊天消息 */
export interface ChatMessage {
  id: string
  role: 'user' | 'ai'
  content: string
  retrievalInfo: RetrievalDoc[]
  rerankInfo: RetrievalDoc[]
  showRetrievalDetails: boolean
  isInterrupted?: boolean
}

/** 模型信息 */
export interface ModelInfo {
  name: string
  description?: string
  model?: string
}

/** 模型列表 */
export interface ModelsData {
  cloud_models: ModelInfo[]
  local_models: ModelInfo[]
}

/** 会话 */
export interface SessionItem {
  session_id: string
  title: string
  updated_at: string
  message_count: number
}

/** 快捷提示 */
export interface QuickTip {
  id: number
  text: string
}
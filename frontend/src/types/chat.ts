/** 检索结果文档 */
export interface RetrievalDoc {
  index: number
  source: string
  score?: number
  content_preview?: string
  content?: string
}

/** RAG 管道阶段 */
export interface PipelineStage {
  name: string
  label: string
  description: string
  input: Record<string, unknown>
  output: Record<string, unknown>
  duration_ms: number | null
}

/** RAG 管道阶段定义（来自 /api/pipeline/stages） */
export interface PipelineStageDefinition {
  order: number
  name: string
  label: string
  description: string
  input: string
  output: string
  config_keys: string[]
  module: string
  current_config: Record<string, unknown>
}

/** 文档分块 */
export interface ChunkItem {
  id: string
  content: string
  metadata: Record<string, unknown>
  content_length: number
}

/** 文档来源 */
export interface SourceItem {
  name: string
  chunk_count: number
}

/** 聊天消息 */
export interface ChatMessage {
  id: string
  role: 'user' | 'ai'
  content: string
  retrievalInfo: RetrievalDoc[]
  rerankInfo: RetrievalDoc[]
  pipelineStages: PipelineStage[]
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
import { ref, nextTick, onMounted, onBeforeUnmount, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useSettingsStore } from '../stores/settings'
import type { ChatMessage, ModelsData, QuickTip } from '../types/chat'

let _msgIdCounter = 0
function nextMsgId(): string {
  return `msg-${Date.now()}-${++_msgIdCounter}`
}

export function useChat(externalSessionId?: Ref<string | null>) {
  const settings = useSettingsStore()
  const messages = ref<ChatMessage[]>([])
  const inputText = ref('')
  const loading = ref(false)
  const models = ref<ModelsData>({ cloud_models: [], local_models: [] })
  const vectorStoreExists = ref(false)
  const vectorStoreStale = ref(false)
  const connected = ref(false)
  const messagesContainer = ref<HTMLElement | null>(null)
  const showRetrievalResults = ref(true)
  const useStreaming = ref(true)
  const lastQuestion = ref('')
  const abortController = ref<AbortController | null>(null)
  // 如果外部传入 sessionId ref，直接共享引用，避免 watch 异步延迟导致值不同步
  const currentSessionId = externalSessionId ?? ref<string | null>(null)

  const quickTips = ref<QuickTip[]>([
    { id: 1, text: '总结文档内容' },
    { id: 2, text: '提取关键信息' },
    { id: 3, text: '回答具体问题' },
    { id: 4, text: '列出文档要点' },
  ])

  // ---- 初始化 ----
  async function checkConnection(): Promise<void> {
    try {
      const res = await api.healthCheck()
      connected.value = res.data.status === 'ok'
    } catch {
      connected.value = false
    }
  }

  async function loadModels(): Promise<void> {
    try {
      const res = await api.getModels()
      models.value = res.data as ModelsData
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      ElMessage.error('加载模型列表失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function checkVectorStore(): Promise<void> {
    try {
      const res = await api.getVectorStoreStatus()
      vectorStoreExists.value = res.data.exists as boolean
      vectorStoreStale.value = Boolean(res.data.stale)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      ElMessage.error('检查知识库状态失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  function getSelectedModelInfo(): ModelsData['cloud_models'][0] | ModelsData['local_models'][0] | undefined {
    const allModels = [...models.value.cloud_models, ...models.value.local_models]
    return allModels.find((m) => m.name === settings.selectedModel)
  }

  async function ensureModelReady(): Promise<void> {
    const modelName = settings.selectedModel
    if (!modelName) {
      ElMessage.warning('请先选择模型')
      throw new Error('请先选择模型')
    }
    const modelInfo = getSelectedModelInfo()
    if (!modelInfo) {
      ElMessage.warning('模型信息不存在')
      throw new Error('模型信息不存在')
    }
    try {
      await api.preloadModelRuntime({
        model: modelName,
        use_reranker: settings.useReranker,
      })
    } catch {
      // 预热失败不阻塞
    }
  }

  // ---- 滚动 ----
  let _scrollRafPending = false
  async function scrollToBottom(): Promise<void> {
    if (_scrollRafPending) return
    _scrollRafPending = true
    requestAnimationFrame(() => {
      _scrollRafPending = false
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  }

  // ---- 向量库状态同步 ----
  function handleVectorStoreChanged(event: Event): void {
    const detail = (event as CustomEvent).detail as { exists: boolean; stale: boolean } | undefined
    if (detail) {
      vectorStoreExists.value = detail.exists
      vectorStoreStale.value = detail.stale
    }
  }

  onMounted(() => {
    window.addEventListener('vectorstore:changed', handleVectorStoreChanged)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('vectorstore:changed', handleVectorStoreChanged)
  })

  function toggleRetrievalDetails(idx: number): void {
    messages.value[idx].showRetrievalDetails = !messages.value[idx].showRetrievalDetails
  }

  // ---- 通过 ID 查找消息索引 ----
  function findMsgIndexById(id: string): number {
    return messages.value.findIndex(m => m.id === id)
  }

  // ---- 等待流式请求真正停止 ----
  async function waitForStreamingStop(): Promise<void> {
    // 等待 abortController 被清空（在 sendStreamingMessage 的 finally 块中执行）
    const maxWait = 2000
    const interval = 50
    let waited = 0
    while (abortController.value !== null && waited < maxWait) {
      await new Promise(resolve => setTimeout(resolve, interval))
      waited += interval
    }
  }

  // ---- 发送消息 ----
  async function sendNormalMessage(question: string, targetMsgId?: string): Promise<void> {
    const res = await api.query({
      question,
      model: settings.selectedModel,
      temperature: settings.temperature,
      max_tokens: settings.maxTokens,
      top_k: settings.topK,
      use_reranker: settings.useReranker,
      reranker_top_n: settings.rerankerTopN,
      session_id: currentSessionId.value || '',
    })

    const answer = (res.data.answer ?? '') as string
    const retrievalInfo = ((res.data.retrieval_info ?? []) as ChatMessage['retrievalInfo']).map(
      (d: ChatMessage['retrievalInfo'][0], i: number) => ({ ...d, index: i })
    )
    const rerankInfo = ((res.data.rerank_info ?? []) as ChatMessage['rerankInfo'])
    const pipelineStages = ((res.data.pipeline_stages ?? []) as ChatMessage['pipelineStages'])

    if (targetMsgId !== undefined) {
      // 重新生成：更新已有占位消息
      const idx = findMsgIndexById(targetMsgId)
      if (idx !== -1) {
        lastQuestion.value = question
        messages.value[idx].content = answer
        messages.value[idx].retrievalInfo = retrievalInfo
        messages.value[idx].rerankInfo = rerankInfo
        messages.value[idx].pipelineStages = pipelineStages
        messages.value[idx].showRetrievalDetails = false
        messages.value[idx].isInterrupted = false
        return
      }
      // ID 找不到（理论上不应发生），fallback 到插入
    }

    // 已有空占位消息时更新，否则 push 新消息
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.role === 'ai' && lastMsg.content === '') {
      lastMsg.content = answer
      lastMsg.retrievalInfo = retrievalInfo
      lastMsg.rerankInfo = rerankInfo
      lastMsg.pipelineStages = pipelineStages
      lastMsg.showRetrievalDetails = false
      lastMsg.isInterrupted = false
    } else {
      messages.value.push({
        id: nextMsgId(),
        role: 'ai',
        content: answer,
        retrievalInfo,
        rerankInfo,
        pipelineStages,
        showRetrievalDetails: false,
      })
    }
  }

  async function sendStreamingMessage(question: string, targetMsgId?: string): Promise<void> {
    const controller = new AbortController()
    abortController.value = controller

    // 创建占位 AI 消息
    const aiMsgId = targetMsgId ?? nextMsgId()
    if (targetMsgId !== undefined) {
      // 重新生成：在指定位置插入占位
      const targetIdx = findMsgIndexById(targetMsgId)
      if (targetIdx !== -1) {
        // 已有占位消息，清空内容
        messages.value[targetIdx].content = ''
        messages.value[targetIdx].retrievalInfo = []
        messages.value[targetIdx].rerankInfo = []
        messages.value[targetIdx].pipelineStages = []
        messages.value[targetIdx].isInterrupted = false
      }
      lastQuestion.value = question
    } else {
      messages.value.push({
        id: aiMsgId,
        role: 'ai',
        content: '',
        retrievalInfo: [],
        rerankInfo: [],
        pipelineStages: [],
        showRetrievalDetails: false,
      })
    }

    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null

    try {
      const res = await api.queryStreamPost({
        question,
        model: settings.selectedModel,
        temperature: settings.temperature,
        max_tokens: settings.maxTokens,
        top_k: settings.topK,
        use_reranker: settings.useReranker,
        reranker_top_n: settings.rerankerTopN,
        session_id: currentSessionId.value || '',
      }, controller.signal)

      const body = res.body as ReadableStream<Uint8Array>
      reader = body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamedContentLength = 0

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          // 流结束：处理 buffer 中残留的非完整事件（忽略，因无 \n\n 终止符）
          break
        }

        buffer += decoder.decode(value, { stream: true })

        // 按 SSE 事件边界（\n\n）提取完整事件
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const eventEnd = buffer.indexOf('\n\n')
          if (eventEnd === -1) break

          const rawEvent = buffer.slice(0, eventEnd)
          buffer = buffer.slice(eventEnd + 2)

          // 合并事件中所有 data: 行（SSE 规范：多行 data 字段用 \n 连接）
          const dataLines: string[] = []
          for (const line of rawEvent.split('\n')) {
            if (line.startsWith('data:')) {
              const trimmed = line.slice(5).trimStart()
              dataLines.push(trimmed)
            }
          }
          const jsonStr = dataLines.join('\n')
          if (!jsonStr || jsonStr === '[DONE]') continue

          try {
            const data = JSON.parse(jsonStr)
            const msgIdx = findMsgIndexById(aiMsgId)
            if (msgIdx === -1) continue

            if (data.done) {
              if (data.retrieval_info) {
                messages.value[msgIdx].retrievalInfo = data.retrieval_info.map(
                  (d: ChatMessage['retrievalInfo'][0], i: number) => ({ ...d, index: i })
                )
              }
              if (data.rerank_info) {
                messages.value[msgIdx].rerankInfo = data.rerank_info
              }
              if (data.pipeline_stages) {
                messages.value[msgIdx].pipelineStages = data.pipeline_stages
              }
            } else if (data.chunk) {
              messages.value[msgIdx].content += data.chunk
              streamedContentLength += data.chunk.length
              await scrollToBottom()
            }
          } catch (parseErr) {
            console.warn('[SSE] JSON 解析失败:', jsonStr.slice(0, 80))
          }
        }
      }

      // 流式完成 - 流式中途中断则降级
      const msgIdx = findMsgIndexById(aiMsgId)
      if (msgIdx !== -1 && streamedContentLength === 0 && messages.value[msgIdx].content === '') {
        // 占位消息仍在，降级到普通请求（sendNormalMessage 会通过 ID 找到并更新它）
        await sendNormalMessage(question, aiMsgId)
      }
    } catch (e: unknown) {
      // Reader 已被手动 abort（用户点击停止），直接清理占位
      if (senderErrorIsAbort(e)) {
        // 保留已有内容
        return
      }
      // 流式失败：通过 ID 查找消息
      const msgIdx = findMsgIndexById(aiMsgId)
      if (msgIdx !== -1 && messages.value[msgIdx].role === 'ai') {
        const partialContent = messages.value[msgIdx].content
        if (!partialContent) {
          // 空占位消息，降级到普通请求（保留占位，sendNormalMessage 会更新它）
          await sendNormalMessage(question, aiMsgId)
        }
        // 有部分内容则保留，不降级
      }
    } finally {
      reader?.releaseLock()
      abortController.value = null
    }
  }

  async function sendMessageInternal(question: string, targetMsgId?: string): Promise<void> {
    try {
      await ensureModelReady()

      if (useStreaming.value) {
        await sendStreamingMessage(question, targetMsgId)
      } else {
        await sendNormalMessage(question, targetMsgId)
      }
    } catch (e: unknown) {
      // 异常时清理未完成的 AI 占位消息
      if (targetMsgId) {
        const idx = findMsgIndexById(targetMsgId)
        if (idx !== -1 && messages.value[idx].role === 'ai' && messages.value[idx].content === '') {
          messages.value.splice(idx, 1)
        }
      } else {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'ai' && lastMsg.content === '') {
          messages.value.pop()
        }
      }
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      ElMessage.error(err.response?.data?.detail || (e instanceof Error ? e.message : '查询失败'))
      loading.value = false
    }
  }

  async function sendMessage(sessionOps: { ensureSession: () => Promise<void> }): Promise<void> {
    if (!inputText.value.trim()) return

    if (!vectorStoreExists.value) {
      ElMessage.warning('请先在文档管理页面构建知识库')
      return
    }
    if (vectorStoreStale.value) {
      ElMessage.warning('文档已变更，请先重新构建知识库')
      return
    }

    // 中止正在进行的流式请求，防止并发竞态
    if (loading.value) {
      stopStreaming()
      await waitForStreamingStop()
    }

    await sessionOps.ensureSession()

    const question = inputText.value.trim()
    inputText.value = ''
    lastQuestion.value = question
    messages.value.push({ id: nextMsgId(), role: 'user', content: question, retrievalInfo: [], rerankInfo: [], pipelineStages: [], showRetrievalDetails: false })
    loading.value = true

    try {
      await scrollToBottom()
      await sendMessageInternal(question)
    } finally {
      loading.value = false
    }
  }

  // ---- 重新生成 ----
  async function regenerateMessage(msgIdx: number): Promise<void> {
    // 找到该 AI 回复对应的用户提问（向前查找最近的 user 消息）
    let question = ''
    for (let i = msgIdx - 1; i >= 0; i--) {
      if (messages.value[i].role === 'user') {
        question = messages.value[i].content
        break
      }
    }
    if (!question) {
      ElMessage.warning('无法重新生成：未找到对应的提问')
      return
    }
    if (!vectorStoreExists.value) {
      ElMessage.warning('请先在文档管理页面构建知识库')
      return
    }
    if (vectorStoreStale.value) {
      ElMessage.warning('文档已变更，请先重新构建知识库')
      return
    }
    // 中止正在进行的流式请求
    if (loading.value) {
      stopStreaming()
      await waitForStreamingStop()
    }
    // 移除旧 AI 消息，创建新的占位消息（ID 在 sendStreamingMessage 中使用）
    messages.value.splice(msgIdx, 1)
    const newAiMsgId = nextMsgId()
    messages.value.splice(msgIdx, 0, {
      id: newAiMsgId,
      role: 'ai',
      content: '',
      retrievalInfo: [],
      rerankInfo: [],
      pipelineStages: [],
      showRetrievalDetails: false,
    })
    loading.value = true
    try {
      await sendMessageInternal(question, newAiMsgId)
    } finally {
      loading.value = false
    }
  }

  // ---- 停止 + 继续 ----
  function stopStreaming(targetMsgId?: string): void {
    const controller = abortController.value
    if (controller) {
      controller.abort()
      abortController.value = null
    }
    loading.value = false

    // 通过 ID 或默认取最后一条 AI 消息
    let targetMsg: ChatMessage | undefined
    if (targetMsgId) {
      const idx = findMsgIndexById(targetMsgId)
      if (idx !== -1) targetMsg = messages.value[idx]
    } else {
      // 默认：找最后一条正在生成的 AI 消息
      for (let i = messages.value.length - 1; i >= 0; i--) {
        if (messages.value[i].role === 'ai') {
          targetMsg = messages.value[i]
          break
        }
      }
    }

    if (targetMsg && targetMsg.role === 'ai') {
      if (targetMsg.content) {
        targetMsg.isInterrupted = true
      } else {
        // 空内容的占位消息，直接移除
        const idx = findMsgIndexById(targetMsg.id)
        if (idx !== -1) messages.value.splice(idx, 1)
      }
    }
    ElMessage.info('已停止生成')
  }

  async function regenerateInterrupted(): Promise<void> {
    // 找最后一条被中断的 AI 消息
    let targetIdx = -1
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'ai' && messages.value[i].isInterrupted) {
        targetIdx = i
        break
      }
    }
    if (targetIdx === -1) return
    await regenerateMessage(targetIdx)
  }

  // ---- 复制 ----
  async function copyMessage(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text)
      ElMessage.success('已复制到剪贴板')
    } catch {
      const textArea = document.createElement('textarea')
      textArea.value = text
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      ElMessage.success('已复制到剪贴板')
    }
  }

  return {
    // state
    messages, inputText, loading, models, vectorStoreExists, vectorStoreStale,
    connected, messagesContainer, showRetrievalResults, useStreaming,
    lastQuestion, abortController, currentSessionId, quickTips,
    // actions
    checkConnection, loadModels, checkVectorStore, ensureModelReady,
    getSelectedModelInfo, scrollToBottom, toggleRetrievalDetails,
    sendMessage, sendNormalMessage, sendStreamingMessage, sendMessageInternal,
    regenerateMessage, stopStreaming, regenerateInterrupted, copyMessage,
    waitForStreamingStop,
  }
}

function senderErrorIsAbort(e: unknown): boolean {
  if (e instanceof DOMException && e.name === 'AbortError') return true
  if (e instanceof TypeError && (e.message.includes('abort') || e.message.includes('AbortError'))) return true
  return false
}
<template>
  <div class="chat-page">
    <div class="chat-layout">
      <!-- 移动端遮罩层 -->
      <div
        v-if="showSessionSidebar || showSettingsSidebar"
        class="mobile-overlay"
        @click="closeMobileSidebars"
      />

      <!-- 会话列表侧边栏 -->
      <SessionSidebar
        v-model:search-text="sessionOps.sessionsSearch.value"
        :model-value="showSessionSidebar"
        :all-sessions="sessionOps.sessions.value"
        :filtered-sessions="sessionOps.filteredSessions.value"
        :loading="sessionOps.loadingSessions.value"
        :current-session-id="sessionOps.currentSessionId.value"
        :display-count="sessionOps.sessionsDisplayCount.value"
        @create-new-session="handleCreateNewSession"
        @select-session="handleSelectSession"
        @rename-session="(session) => sessionOps.renameSession(session.session_id, session.title)"
        @delete-session="handleDeleteSession"
        @load-more-sessions="sessionOps.loadMoreSessions"
      />

      <!-- 主聊天区域 -->
      <div class="chat-main">
        <!-- 顶栏 -->
        <div class="chat-header">
          <el-button
            class="menu-btn mobile-only"
            :icon="ChatDotRound"
            @click="showSessionSidebar = !showSessionSidebar"
          />
          <div class="header-title-wrap">
            <h2 class="header-title">
              RAG 知识库问答
            </h2>
            <div class="header-status">
              <span
                class="header-status-dot"
                :class="chat.connected.value ? 'online' : 'offline'"
              />
              <span>{{ chat.connected.value ? '在线' : '离线' }}</span>
              <span class="header-status-sep">|</span>
              <span>{{ chat.vectorStoreExists.value ? '知识库就绪' : '知识库未构建' }}</span>
            </div>
          </div>
          <el-button
            class="menu-btn mobile-only"
            :icon="Operation"
            @click="showSettingsSidebar = !showSettingsSidebar"
          />
        </div>

        <!-- 消息区 -->
        <div
          ref="messagesContainer"
          class="messages-container"
        >
          <!-- 空状态 -->
          <div
            v-if="chat.messages.value.length === 0"
            class="empty-state"
          >
            <div class="empty-icon">
              <svg
                viewBox="0 0 80 80"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <circle
                  cx="40"
                  cy="40"
                  r="35"
                  stroke="url(#gradEmpty)"
                  stroke-width="2"
                  opacity="0.5"
                />
                <path
                  d="M30 38L36 44L50 30"
                  stroke="url(#gradEmpty)"
                  stroke-width="3"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
                <defs>
                  <linearGradient
                    id="gradEmpty"
                    x1="0%"
                    y1="0%"
                    x2="100%"
                    y2="100%"
                  >
                    <stop
                      offset="0%"
                      style="stop-color:#00d4ff"
                    />
                    <stop
                      offset="100%"
                      style="stop-color:#7b2cbf"
                    />
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <h2>开始与 AI 对话</h2>
            <p>上传您的文档，构建知识库，然后开始提问吧！</p>
          </div>

          <!-- 消息列表 -->
          <ChatMessage
            v-for="(msg, idx) in chat.messages.value"
            :key="msg.id"
            :msg="msg"
            :idx="idx"
            :show-retrieval="chat.showRetrievalResults.value"
            @copy="chat.copyMessage"
            @regenerate="chat.regenerateMessage"
            @continue="chat.regenerateInterrupted"
            @toggle-retrieval="chat.toggleRetrievalDetails"
          />

          <!-- 加载指示器（仅非流式模式使用，流式模式由占位消息提供视觉反馈） -->
          <div
            v-if="chat.loading.value && !chat.useStreaming.value"
            class="message ai loading"
          >
            <div class="message-avatar">
              <svg
                viewBox="0 0 32 32"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <circle
                  cx="16"
                  cy="16"
                  r="14"
                  stroke="url(#gradLoad)"
                  stroke-width="2"
                />
                <path
                  d="M10 16L14 20L22 12"
                  stroke="url(#gradLoad)"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
                <defs>
                  <linearGradient
                    id="gradLoad"
                    x1="0%"
                    y1="0%"
                    x2="100%"
                    y2="100%"
                  >
                    <stop
                      offset="0%"
                      style="stop-color:#00d4ff"
                    />
                    <stop
                      offset="100%"
                      style="stop-color:#7b2cbf"
                    />
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <div class="message-content">
              <div class="message-role">
                AI 助手
              </div>
              <div
                v-if="chat.useStreaming.value"
                class="typing-indicator"
              >
                <span />
                <span />
                <span />
              </div>
              <div
                v-else
                class="message-text loading-text"
              >
                正在思考中...
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <ChatInput
          v-model="chat.inputText.value"
          :loading="chat.loading.value"
          @send="chat.sendMessage({ ensureSession: ensureSession })"
          @stop="chat.stopStreaming"
        />
      </div>

      <!-- 设置侧边栏 -->
      <SettingsSidebar
        :model-value="showSettingsSidebar"
        :connected="chat.connected.value"
        :vector-store-exists="chat.vectorStoreExists.value"
        :vector-store-stale="chat.vectorStoreStale.value"
        :models="chat.models.value"
        :selected-model="settings.selectedModel"
        :use-reranker="settings.useReranker"
        :reranker-top-n="settings.rerankerTopN"
        :temperature="settings.temperature"
        :max-tokens="settings.maxTokens"
        :top-k="settings.topK"
        :show-retrieval-results="chat.showRetrievalResults.value"
        :use-streaming="chat.useStreaming.value"
        :quick-tips="chat.quickTips.value"
        @update:selected-model="(v) => settings.selectedModel = v"
        @update:use-reranker="(v) => settings.useReranker = v"
        @update:reranker-top-n="(v) => settings.rerankerTopN = v"
        @update:temperature="(v) => settings.temperature = v"
        @update:max-tokens="(v) => settings.maxTokens = v"
        @update:top-k="(v) => settings.topK = v"
        @update:show-retrieval-results="(v) => chat.showRetrievalResults.value = v"
        @update:use-streaming="(v) => chat.useStreaming.value = v"
        @send-quick-tip="handleQuickTip"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ChatDotRound, Operation } from '@element-plus/icons-vue'
import { useSettingsStore } from '../stores/settings'
import { useChat } from '../composables/useChat'
import { useSessions } from '../composables/useSessions'
import type { ChatMessage as ChatMessageType } from '../types/chat'
import SessionSidebar from '../components/chat/SessionSidebar.vue'
import SettingsSidebar from '../components/chat/SettingsSidebar.vue'
import ChatMessage from '../components/chat/ChatMessage.vue'
import ChatInput from '../components/chat/ChatInput.vue'

// ---- 核心 composables ----
const settings = useSettingsStore()
const sessionOps = useSessions()
// 共享 currentSessionId ref，确保 useChat 闭包和 sessionOps 操作的是同一个引用
const chat = useChat(sessionOps.currentSessionId)

// ---- 移动端侧边栏 ----
const showSessionSidebar = ref(false)
const showSettingsSidebar = ref(false)

function closeMobileSidebars(): void {
  showSessionSidebar.value = false
  showSettingsSidebar.value = false
}

// ---- 会话操作 ----
async function handleCreateNewSession(): Promise<void> {
  await sessionOps.createNewSession(chat.messages.value.length)
  // 创建新会话后清空消息列表，避免旧消息残留
  chat.messages.value = []
  chat.lastQuestion.value = ''
}

async function ensureSession(): Promise<void> {
  if (!sessionOps.currentSessionId.value) {
    await sessionOps.createNewSession(0)
  }
}

async function handleSelectSession(sessionId: string): Promise<void> {
  // 切换会话前先中止正在进行的流式请求，防止旧请求回调污染新会话消息
  if (chat.loading.value) {
    chat.stopStreaming()
    await new Promise(resolve => setTimeout(resolve, 50))
  }

  const data = await sessionOps.loadSession(sessionId)
  if (data?.messages) {
    // 后端返回 snake_case 字段，前端使用 camelCase，需要显式映射
    const rawMessages = data.messages as Array<Record<string, unknown>>
    chat.messages.value = rawMessages.map((m, i) => ({
      id: (m.id as string) || `hist-${Date.now()}-${i}`,
      role: m.role as 'user' | 'ai',
      content: m.content as string,
      retrievalInfo: (m.retrieval_info ?? m.retrievalInfo ?? []) as ChatMessageType['retrievalInfo'],
      rerankInfo: (m.rerank_info ?? m.rerankInfo ?? []) as ChatMessageType['rerankInfo'],
      showRetrievalDetails: false,
    }))
    chat.lastQuestion.value = chat.messages.value
      .filter((m) => m.role === 'user')
      .map((m) => m.content)
      .pop() ?? ''
  } else if (data !== null) {
    // 会话存在但无历史消息
    chat.messages.value = []
    chat.lastQuestion.value = ''
  }
  // data === null 表示加载失败或已是当前会话，不做任何变更
}

async function handleDeleteSession(sessionId: string): Promise<void> {
  const result = await sessionOps.deleteSession(sessionId)
  // 删除的是当前会话时，清空消息列表
  if (result?.wasCurrent) {
    chat.messages.value = []
    chat.lastQuestion.value = ''
  }
}

// ---- 快速提示 ----
function handleQuickTip(text: string): void {
  chat.inputText.value = text
  chat.sendMessage({ ensureSession })
}

// ---- 生命周期 ----
onMounted(async () => {
  chat.checkConnection()
  chat.loadModels()
  chat.checkVectorStore()
  // 必须等待会话列表加载完成，才能恢复 currentSessionId，避免 ensureSession 重复创建
  await sessionOps.loadSessions()
})

onBeforeUnmount(() => {
  if (chat.abortController.value) {
    chat.abortController.value.abort()
  }
})
</script>

<style scoped>
/* === 布局（保留在此，page-level） === */
.chat-page {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-layout {
  display: flex;
  gap: 20px;
  height: 100%;
  min-height: 0;
}

/* === 子组件容器样式（作为 CSS component） === */
.session-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-sidebar {
  width: 300px;
  flex-shrink: 0;
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 212, 255, 0.45) transparent;
}

/* === 主聊天区域 === */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.chat-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--glass-border);
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-btn {
  color: var(--text-muted) !important;
  border: none !important;
  background: transparent !important;
}

.header-title-wrap {
  flex: 1;
}

.header-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.header-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.header-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.header-status-dot.online {
  background: var(--accent-tertiary);
  box-shadow: 0 0 6px var(--accent-tertiary);
}

.header-status-dot.offline {
  background: var(--accent-warning);
  box-shadow: 0 0 6px var(--accent-warning);
}

.header-status-sep {
  opacity: 0.4;
}

/* === 消息区 === */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  text-align: center;
}

.empty-icon {
  width: 100px;
  height: 100px;
  opacity: 0.6;
  animation: float 4s ease-in-out infinite;
}

.empty-state h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.empty-state p {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
  max-width: 300px;
}

/* === 消息条（loading 指示器保留在此）=== */
.message {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  animation: messageSlide 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  animation-fill-mode: forwards;
}

@keyframes messageSlide {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.ai.loading .message-avatar svg {
  width: 100%;
  height: 100%;
}

.message-content {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message-role {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 0 4px;
}

.message-text {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--glass-border);
  padding: 14px 18px;
  border-radius: var(--radius-md);
  line-height: 1.7;
  color: var(--text-primary);
  font-size: 14px;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.loading-text {
  opacity: 0.6;
  font-style: italic;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  gap: 6px;
  padding: 14px 18px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00d4ff, #7b2cbf);
  animation: typingBounce 1.4s ease-in-out infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
  30% { transform: translateY(-10px); opacity: 1; }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

/* === 移动端 === */
.mobile-only {
  display: none;
}

.mobile-overlay {
  display: none;
}

@media (max-width: 1024px) {
  .mobile-only { display: inline-flex; }
  .session-sidebar { position: fixed; left: -280px; top: 0; bottom: 0; z-index: 100; transition: left 0.3s ease; }
  .session-sidebar.mobile-open { left: 0; }
  .chat-sidebar { position: fixed; right: -320px; top: 0; bottom: 0; z-index: 100; transition: right 0.3s ease; }
  .chat-sidebar.mobile-open { right: 0; }
  .mobile-overlay { display: block; position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); z-index: 99; }
  .chat-layout { gap: 0; }
}

@media (max-width: 640px) {
  .messages-container { padding: 16px; gap: 16px; }
  .message-content { max-width: 90%; }
  .chat-header { padding: 12px 16px; }
}
</style>
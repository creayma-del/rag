<template>
  <div
    :class="['message', msg.role]"
    :style="idx >= 3 ? {} : { animationDelay: `${idx * 0.1}s` }"
  >
    <div class="message-avatar">
      <el-icon v-if="msg.role === 'user'">
        <User />
      </el-icon>
      <svg
        v-else
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle
          cx="16"
          cy="16"
          r="14"
          :stroke="`url(#grad-${msg.id})`"
          stroke-width="2"
        />
        <path
          d="M10 16L14 20L22 12"
          :stroke="`url(#grad-${msg.id})`"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <defs>
          <linearGradient
            :id="`grad-${msg.id}`"
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
        {{ msg.role === 'user' ? '你' : 'AI 助手' }}
      </div>
      <!-- 用户消息 -->
      <div
        v-if="msg.role === 'user'"
        class="message-text"
      >
        {{ msg.content }}
      </div>
      <!-- AI 消息 -->
      <template v-else>
        <div
          v-if="msg.content"
          class="message-text markdown-body"
          v-html="renderedHtml"
        />
        <!-- AI 消息内容为空时（流式占位），显示打字动画 -->
        <div
          v-else
          class="typing-indicator"
        >
          <span />
          <span />
          <span />
        </div>
      </template>
      <!-- 操作按钮 -->
      <div
        v-if="msg.role === 'ai' && msg.content"
        class="message-actions"
      >
        <el-button
          size="small"
          text
          class="action-btn"
          @click="$emit('copy', msg.content)"
        >
          <el-icon><CopyDocument /></el-icon>
          <span>复制</span>
        </el-button>
        <el-button
          size="small"
          text
          class="action-btn"
          @click="$emit('regenerate', idx)"
        >
          <el-icon><Refresh /></el-icon>
          <span>重新生成</span>
        </el-button>
        <el-button
          v-if="msg.isInterrupted"
          size="small"
          text
          class="action-btn continue-btn"
          @click="$emit('regenerate-interrupted')"
        >
          <el-icon><ArrowRight /></el-icon>
          <span>重新生成</span>
        </el-button>
      </div>

      <!-- 检索结果 -->
      <div
        v-if="msg.role === 'ai' && msg.retrievalInfo.length > 0 && showRetrieval"
        class="retrieval-results"
      >
        <div
          class="retrieval-header"
          @click="$emit('toggleRetrieval', idx)"
        >
          <div class="retrieval-title">
            <el-icon><Document /></el-icon>
            <span>检索到的相关文档片段 ({{ msg.retrievalInfo.length }} 个)</span>
          </div>
          <el-icon :class="['expand-icon', { expanded: msg.showRetrievalDetails }]">
            <ArrowRight />
          </el-icon>
        </div>
        <div
          v-if="msg.showRetrievalDetails"
          class="retrieval-list"
        >
          <div
            v-for="(doc, docIdx) in msg.retrievalInfo"
            :key="docIdx"
            class="retrieval-item"
          >
            <div class="retrieval-item-header">
              <span class="retrieval-index">#{{ doc.index + 1 }}</span>
              <span class="retrieval-source">{{ doc.source }}</span>
              <el-tag
                v-if="doc.score !== undefined"
                size="small"
                type="success"
              >
                分数: {{ (doc.score * 100).toFixed(1) }}%
              </el-tag>
            </div>
            <div class="retrieval-content">
              {{ doc.content_preview || doc.content || '' }}
            </div>
          </div>
        </div>
      </div>

      <!-- Reranker 结果详情 -->
      <div
        v-if="msg.role === 'ai' && msg.rerankInfo.length > 0 && showRetrieval"
        class="rerank-comparison"
      >
        <div
          class="rerank-header"
          @click="showRerankDetail = !showRerankDetail"
        >
          <div style="display:flex;align-items:center;gap:8px">
            <el-icon><RefreshRight /></el-icon>
            <span>经过 Reranker 重排序后的结果 ({{ msg.rerankInfo.length }} 个)</span>
          </div>
          <el-icon :class="['expand-icon', { expanded: showRerankDetail }]">
            <ArrowRight />
          </el-icon>
        </div>
        <div v-if="showRerankDetail" class="rerank-list">
          <div
            v-for="(doc, docIdx) in msg.rerankInfo"
            :key="docIdx"
            class="retrieval-item"
          >
            <div class="retrieval-item-header">
              <span class="retrieval-index">#{{ doc.index + 1 }}</span>
              <span class="retrieval-source">{{ doc.source }}</span>
              <el-tag
                v-if="doc.score !== undefined"
                size="small"
                type="warning"
              >
                Rerank: {{ doc.score.toFixed(4) }}
              </el-tag>
            </div>
            <div class="retrieval-content">
              {{ doc.content_preview || doc.content || '' }}
            </div>
          </div>
        </div>
      </div>

      <!-- RAG 管道阶段详情 -->
      <div
        v-if="msg.role === 'ai' && msg.pipelineStages.length > 0 && showRetrieval"
        class="pipeline-stages"
      >
        <div
          class="pipeline-stages-header"
          @click="showPipelineDetail = !showPipelineDetail"
        >
          <div style="display:flex;align-items:center;gap:8px">
            <span class="pipeline-icon">🔧</span>
            <span>RAG 管道执行详情 ({{ msg.pipelineStages.length }} 个阶段)</span>
          </div>
          <el-icon :class="['expand-icon', { expanded: showPipelineDetail }]">
            <ArrowRight />
          </el-icon>
        </div>
        <div v-if="showPipelineDetail" class="pipeline-stages-list">
          <div
            v-for="(stage, sIdx) in msg.pipelineStages"
            :key="sIdx"
            class="pipeline-stage-item"
          >
            <div class="stage-item-header">
              <span class="stage-item-order">{{ sIdx + 1 }}</span>
              <span class="stage-item-label">{{ stage.label }}</span>
              <el-tag v-if="stage.duration_ms" size="small" type="info">
                {{ stage.duration_ms }}ms
              </el-tag>
            </div>
            <p class="stage-item-desc">{{ stage.description }}</p>
            <div class="stage-item-io">
              <div class="stage-io-block">
                <span class="io-label">输入</span>
                <span class="io-value">{{ formatStageData(stage.input) }}</span>
              </div>
              <div class="stage-io-block">
                <span class="io-label">输出</span>
                <span class="io-value">{{ formatStageData(stage.output) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { User, CopyDocument, Refresh, ArrowRight, Document, RefreshRight } from '@element-plus/icons-vue'
import type { ChatMessage } from '../../types/chat'

const props = defineProps<{
  msg: ChatMessage
  idx: number
  showRetrieval: boolean
}>()

defineEmits<{
  copy: [text: string]
  regenerate: [msgIdx: number]
  'regenerate-interrupted': []
  toggleRetrieval: [msgIdx: number]
}>()

const renderedHtml = ref('')
const showRerankDetail = ref(false)
const showPipelineDetail = ref(false)

function formatStageData(data: Record<string, unknown>): string {
  return Object.entries(data)
    .map(([k, v]) => {
      const val = Array.isArray(v) ? v.slice(0, 5).join(', ') + (v.length > 5 ? '...' : '') : String(v ?? '-')
      return `${k}: ${val}`
    })
    .join(' | ')
}

watch(
  () => props.msg.content,
  async (content) => {
    if (!content) {
      renderedHtml.value = ''
      return
    }
    try {
      const result = marked.parse(content)
      const rawHtml = result instanceof Promise ? await result : result
      renderedHtml.value = DOMPurify.sanitize(rawHtml)
    } catch {
      renderedHtml.value = DOMPurify.sanitize(content)
    }
  },
  { immediate: true }
)
</script>

<style scoped>
/* 消息条 */
.message {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  animation: messageSlide 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  animation-fill-mode: forwards;
}

.message.user {
  flex-direction: row-reverse;
}

@keyframes messageSlide {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 头像 */
.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.ai .message-avatar {
  background: transparent;
}

.message.user .message-avatar {
  background: rgba(123, 44, 191, 0.15);
  color: var(--accent-secondary);
}

.message-avatar svg {
  width: 100%;
  height: 100%;
}

/* 消息内容区 */
.message-content {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message.user .message-content {
  align-items: flex-end;
}

/* 角色标签 */
.message-role {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 0 4px;
}

/* 消息文本 */
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

.message.user .message-text {
  background: rgba(0, 212, 255, 0.08);
  border-color: rgba(0, 212, 255, 0.25);
}

/* 操作按钮 */
.message-actions {
  display: flex;
  gap: 4px;
  margin-top: 2px;
}

.action-btn {
  color: var(--text-muted) !important;
  font-size: 12px !important;
  padding: 4px 8px !important;
}

.action-btn:hover {
  color: var(--accent-primary) !important;
  background: rgba(0, 212, 255, 0.08) !important;
}

.continue-btn {
  color: var(--accent-tertiary) !important;
}

.continue-btn:hover {
  color: var(--accent-tertiary) !important;
  background: rgba(0, 245, 147, 0.08) !important;
}

/* 检索结果 */
.retrieval-results {
  margin-top: 8px;
  background: rgba(0, 212, 255, 0.03);
  border: 1px solid rgba(0, 212, 255, 0.12);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.retrieval-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.retrieval-header:hover {
  background: rgba(0, 212, 255, 0.05);
}

.retrieval-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.retrieval-title .el-icon {
  color: var(--accent-primary);
}

.expand-icon {
  color: var(--text-muted);
  font-size: 14px;
  transition: transform var(--transition-fast);
}

.expand-icon.expanded {
  transform: rotate(90deg);
}

.retrieval-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 14px 12px;
}

.retrieval-item {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}

.retrieval-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.retrieval-index {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-primary);
}

.retrieval-source {
  font-size: 11px;
  color: var(--text-muted);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.retrieval-content {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
}

/* Reranker 提示 */
.rerank-comparison {
  margin-top: 8px;
  background: rgba(123, 44, 191, 0.05);
  border: 1px solid rgba(123, 44, 191, 0.15);
  border-radius: var(--radius-md);
  padding: 10px 14px;
}

.rerank-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}

.rerank-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 14px 12px;
}

/* 管道阶段详情 */
.pipeline-stages {
  margin-top: 8px;
  background: rgba(0, 245, 147, 0.03);
  border: 1px solid rgba(0, 245, 147, 0.12);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.pipeline-stages-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  transition: background var(--transition-fast);
  font-size: 12px;
  color: var(--text-muted);
}

.pipeline-stages-header:hover {
  background: rgba(0, 245, 147, 0.05);
}

.pipeline-icon {
  font-size: 14px;
}

.pipeline-stages-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 14px 12px;
}

.pipeline-stage-item {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}

.stage-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.stage-item-order {
  font-size: 11px;
  font-weight: 700;
  color: #00f593;
  min-width: 18px;
}

.stage-item-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.stage-item-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 4px 0 8px;
  line-height: 1.4;
}

.stage-item-io {
  display: flex;
  gap: 12px;
}

.stage-io-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.io-label {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}

.io-value {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: monospace;
  word-break: break-all;
  line-height: 1.4;
}

/* Markdown 内容 */
.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 12px 0 8px;
  color: var(--text-primary);
}

.markdown-body :deep(h1) { font-size: 20px; }
.markdown-body :deep(h2) { font-size: 18px; }
.markdown-body :deep(h3) { font-size: 16px; }

.markdown-body :deep(code) {
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--accent-primary);
}

.markdown-body :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: var(--text-secondary);
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--accent-primary);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-muted);
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--glass-border);
  text-align: left;
}

.markdown-body :deep(th) {
  background: rgba(255, 255, 255, 0.04);
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: var(--accent-primary);
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--glass-border);
  margin: 12px 0;
}

.markdown-body :deep(strong) {
  font-weight: 700;
  color: var(--text-primary);
}

/* 打字指示器（流式占位消息） */
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
</style>
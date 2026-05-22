<template>
  <div class="input-area">
    <div class="input-container">
      <textarea
        ref="textareaRef"
        :value="modelValue"
        class="chat-textarea"
        :placeholder="loading ? 'AI 正在生成回复...' : '输入你的问题... (Enter 发送, Shift+Enter 换行)'"
        :disabled="loading"
        :rows="1"
        @input="onInput"
        @keydown.enter.exact.prevent="handleSend"
      />
      <button
        class="action-btn"
        :class="{ 'is-send': !loading, 'is-stop': loading }"
        :disabled="!loading && !modelValue.trim()"
        :aria-label="loading ? '停止生成' : '发送消息'"
        @click="loading ? $emit('stop') : $emit('send')"
      >
        <!-- 发送图标 -->
        <svg
          v-if="!loading"
          class="btn-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <line
            x1="12"
            y1="19"
            x2="12"
            y2="5"
          />
          <polyline points="5 12 12 5 19 12" />
        </svg>
        <!-- 停止图标 -->
        <svg
          v-else
          class="btn-icon stop-icon"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <rect
            x="6"
            y="6"
            width="12"
            height="12"
            rx="2"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = defineProps<{
  modelValue: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  stop: []
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)

function onInput(e: Event): void {
  const target = e.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
  autoResize()
}

function autoResize(): void {
  void nextTick(() => {
    const el = textareaRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  })
}

function handleSend(): void {
  if (!props.loading && props.modelValue.trim()) {
    emit('send')
  }
}

// 外部清空输入后重置高度
watch(() => props.modelValue, () => {
  if (!props.modelValue) {
    void nextTick(() => {
      const el = textareaRef.value
      if (el) el.style.height = 'auto'
    })
  }
})
</script>

<style scoped>
.input-area {
  padding: 16px 24px;
  border-top: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.input-container {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 0;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 8px 12px 8px 20px;
  transition:
    border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    background 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.input-container:focus-within {
  border-color: rgba(0, 212, 255, 0.5);
  background: rgba(255, 255, 255, 0.06);
  box-shadow:
    0 0 0 4px rgba(0, 212, 255, 0.08),
    0 0 30px rgba(0, 212, 255, 0.06);
}

.chat-textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.6;
  font-family: inherit;
  padding: 6px 0;
  min-height: 24px;
  max-height: 160px;
  overflow-y: hidden;
}

.chat-textarea::placeholder {
  color: rgba(255, 255, 255, 0.25);
  transition: color 0.3s ease;
}

.chat-textarea:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.chat-textarea:disabled::placeholder {
  color: rgba(255, 255, 255, 0.12);
}

/* ---- 动作按钮 ---- */
.action-btn {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    all 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1);
  margin-left: 8px;
  position: relative;
  overflow: hidden;
}

/* 发送状态 */
.action-btn.is-send {
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%);
  color: #fff;
  box-shadow:
    0 2px 12px rgba(0, 212, 255, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.action-btn.is-send::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.2), transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.action-btn.is-send:hover::after {
  opacity: 1;
}

.action-btn.is-send:hover {
  transform: scale(1.08);
  box-shadow:
    0 4px 20px rgba(0, 212, 255, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.action-btn.is-send:active {
  transform: scale(0.94);
  transition: transform 0.1s ease;
}

.action-btn.is-send:disabled {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.2);
  box-shadow: none;
  cursor: not-allowed;
  transform: none;
}

.action-btn.is-send:disabled::after {
  display: none;
}

/* 停止状态 */
.action-btn.is-stop {
  background: rgba(255, 107, 107, 0.15);
  color: #ff6b6b;
  border: 1.5px solid rgba(255, 107, 107, 0.3);
  box-shadow: 0 0 0 0 rgba(255, 107, 107, 0);
  animation: stopPulse 2s ease-in-out infinite;
}

.action-btn.is-stop:hover {
  background: rgba(255, 107, 107, 0.25);
  border-color: rgba(255, 107, 107, 0.6);
  transform: scale(1.08);
  box-shadow: 0 4px 20px rgba(255, 107, 107, 0.3);
  animation: none;
}

.action-btn.is-stop:active {
  transform: scale(0.94);
  transition: transform 0.1s ease;
}

@keyframes stopPulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(255, 107, 107, 0);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(255, 107, 107, 0.08);
  }
}

/* 图标 */
.btn-icon {
  width: 18px;
  height: 18px;
  transition: transform 0.2s ease;
}

.action-btn.is-send:hover .btn-icon {
  transform: translateY(-1px);
}

.stop-icon {
  width: 14px;
  height: 14px;
}
</style>
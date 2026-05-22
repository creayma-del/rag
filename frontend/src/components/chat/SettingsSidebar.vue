<template>
  <div :class="['chat-sidebar', { 'mobile-open': modelValue }]">
    <div class="sidebar-header">
      <h3>对话设置</h3>
    </div>

    <div class="sidebar-section">
      <div class="section-title">
        <el-icon><Connection /></el-icon>
        <span>连接状态</span>
      </div>
      <div
        class="status-badge"
        :class="connected ? 'online' : 'offline'"
      >
        <span class="status-dot" />
        <span>{{ connected ? '后端已连接' : '连接断开' }}</span>
      </div>
    </div>

    <div class="sidebar-section">
      <div class="section-title">
        <el-icon><Box /></el-icon>
        <span>知识库</span>
      </div>
      <div
        class="status-badge"
        :class="vectorStoreExists ? 'ready' : 'warning'"
      >
        <span class="status-dot" />
        <span>{{ vectorStoreExists ? '知识库就绪' : (vectorStoreStale ? '索引已过期' : '请先构建') }}</span>
      </div>
    </div>

    <div class="sidebar-section">
      <div class="section-title">
        <el-icon><Cpu /></el-icon>
        <span>选择模型</span>
      </div>
      <div
        ref="selectRef"
        :class="['custom-select', { 'is-open': selectOpen }]"
      >
        <div
          class="select-trigger"
          @click="selectOpen = !selectOpen"
        >
          <span :class="['select-value', { placeholder: !selectedModel }]">
            {{ selectedModel || '搜索或选择模型...' }}
          </span>
          <svg
            :class="['select-arrow', { rotated: selectOpen }]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
        <Transition name="select-dropdown">
          <div
            v-if="selectOpen"
            class="select-dropdown"
          >
            <div class="select-search">
              <svg
                class="search-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <circle
                  cx="11"
                  cy="11"
                  r="8"
                />
                <path d="M21 21l-4.35-4.35" />
              </svg>
              <input
                v-model="searchText"
                class="search-input"
                placeholder="搜索模型..."
                @click.stop
              >
            </div>
            <div class="select-options">
              <template v-if="filteredCloudModels.length">
                <div class="option-group-label">
                  云端模型
                </div>
                <div
                  v-for="model in filteredCloudModels"
                  :key="model.name"
                  :class="['option-item', { active: model.name === selectedModel }]"
                  @click="handleSelect(model.name)"
                >
                  <div class="option-content">
                    <span class="option-name">{{ model.name }}</span>
                    <span class="option-desc">{{ model.description || model.model }}</span>
                  </div>
                  <svg
                    v-if="model.name === selectedModel"
                    class="option-check"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                  >
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              </template>
              <template v-if="filteredLocalModels.length">
                <div class="option-group-label">
                  本地模型
                </div>
                <div
                  v-for="model in filteredLocalModels"
                  :key="model.name"
                  :class="['option-item', { active: model.name === selectedModel }]"
                  @click="handleSelect(model.name)"
                >
                  <div class="option-content">
                    <span class="option-name">{{ model.name }}</span>
                    <span class="option-desc">{{ model.description || model.model }}</span>
                  </div>
                  <svg
                    v-if="model.name === selectedModel"
                    class="option-check"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                  >
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              </template>
              <div
                v-if="!filteredCloudModels.length && !filteredLocalModels.length"
                class="option-empty"
              >
                无匹配模型
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <div class="sidebar-section">
      <div class="section-title">
        <el-icon><Operation /></el-icon>
        <span>高级选项</span>
      </div>
      <div class="setting-item">
        <div class="setting-label">
          启用 Reranker
        </div>
        <el-switch
          :model-value="useReranker"
          active-color="#00d4ff"
          @update:model-value="$emit('update:useReranker', $event)"
        />
      </div>
      <div
        v-if="useReranker"
        class="setting-item"
      >
        <div class="setting-label">
          Reranker Top N
        </div>
        <el-slider
          :model-value="rerankerTopN"
          :min="1"
          :max="10"
          :step="1"
          :marks="{1:'1',5:'5',10:'10'}"
          @update:model-value="$emit('update:rerankerTopN', $event)"
        />
      </div>
      <div class="setting-item">
        <div class="setting-label">
          Temperature
        </div>
        <el-slider
          :model-value="temperature"
          :min="0"
          :max="2"
          :step="0.1"
          @update:model-value="$emit('update:temperature', $event)"
        />
      </div>
      <div class="setting-item">
        <div class="setting-label">
          Max Tokens
        </div>
        <el-input-number
          :model-value="maxTokens"
          :min="256"
          :max="8192"
          :step="256"
          style="width: 100%"
          @update:model-value="$emit('update:maxTokens', $event)"
        />
      </div>
      <div class="setting-item">
        <div class="setting-label">
          Top K
        </div>
        <el-slider
          :model-value="topK"
          :min="1"
          :max="10"
          :step="1"
          :marks="{1:'1',5:'5',10:'10'}"
          @update:model-value="$emit('update:topK', $event)"
        />
      </div>
    </div>

    <div class="sidebar-section">
      <div class="section-title">
        <el-icon><View /></el-icon>
        <span>显示设置</span>
      </div>
      <div class="setting-item">
        <div class="setting-label">
          显示检索结果
        </div>
        <el-switch
          :model-value="showRetrievalResults"
          active-color="#00d4ff"
          @update:model-value="$emit('update:showRetrievalResults', $event)"
        />
      </div>
      <div class="setting-item">
        <div class="setting-label">
          流式响应
        </div>
        <el-switch
          :model-value="useStreaming"
          active-color="#00d4ff"
          @update:model-value="$emit('update:useStreaming', $event)"
        />
      </div>
    </div>

    <div class="sidebar-section quick-tips">
      <div class="section-title">
        <el-icon><MagicStick /></el-icon>
        <span>快速提示</span>
      </div>
      <div class="tips-list">
        <div
          v-for="tip in quickTips"
          :key="tip.id"
          class="tip-item"
          @click="$emit('sendQuickTip', tip.text)"
        >
          {{ tip.text }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Connection, Box, Cpu, MagicStick, Operation, View } from '@element-plus/icons-vue'
import type { ModelsData, QuickTip } from '../../types/chat'

const props = defineProps<{
  modelValue: boolean
  connected: boolean
  vectorStoreExists: boolean
  vectorStoreStale: boolean
  models: ModelsData
  selectedModel: string
  useReranker: boolean
  rerankerTopN: number
  temperature: number
  maxTokens: number
  topK: number
  showRetrievalResults: boolean
  useStreaming: boolean
  quickTips: QuickTip[]
}>()

const emit = defineEmits<{
  'update:selectedModel': [value: string]
  'update:useReranker': [value: boolean]
  'update:rerankerTopN': [value: number]
  'update:temperature': [value: number]
  'update:maxTokens': [value: number]
  'update:topK': [value: number]
  'update:showRetrievalResults': [value: boolean]
  'update:useStreaming': [value: boolean]
  sendQuickTip: [text: string]
}>()

// ---- 自定义模型选择器 ----
const selectRef = ref<HTMLElement | null>(null)
const selectOpen = ref(false)
const searchText = ref('')

const filteredCloudModels = computed(() => {
  const q = searchText.value.toLowerCase().trim()
  if (!q) return props.models.cloud_models
  return props.models.cloud_models.filter(
    (m) => m.name.toLowerCase().includes(q) || (m.description || m.model || '').toLowerCase().includes(q),
  )
})

const filteredLocalModels = computed(() => {
  const q = searchText.value.toLowerCase().trim()
  if (!q) return props.models.local_models
  return props.models.local_models.filter(
    (m) => m.name.toLowerCase().includes(q) || (m.description || m.model || '').toLowerCase().includes(q),
  )
})

function handleSelect(name: string) {
  emit('update:selectedModel', name)
  selectOpen.value = false
  searchText.value = ''
}

function handleClickOutside(e: MouseEvent) {
  if (selectRef.value && !selectRef.value.contains(e.target as Node)) {
    selectOpen.value = false
    searchText.value = ''
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
/* 根元素（宽/背景/圆角/布局由父组件 Chat.vue scoped 控制，此处定义内部样式） */
.sidebar-header {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--glass-border);
  margin-bottom: 4px;
  flex-shrink: 0;
}

.sidebar-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* 分区 */
.sidebar-section {
  padding: 16px 0;
  border-bottom: 1px solid var(--glass-border);
}

.sidebar-section:last-child {
  border-bottom: none;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-title .el-icon {
  color: var(--accent-primary);
}

/* 状态徽章 */
.status-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
}

.status-badge.online,
.status-badge.ready {
  background: rgba(0, 245, 147, 0.08);
  color: var(--accent-tertiary);
  border: 1px solid rgba(0, 245, 147, 0.2);
}

.status-badge.offline {
  background: rgba(255, 107, 107, 0.08);
  color: var(--accent-danger);
  border: 1px solid rgba(255, 107, 107, 0.2);
}

.status-badge.warning {
  background: rgba(255, 217, 61, 0.08);
  color: var(--accent-warning);
  border: 1px solid rgba(255, 217, 61, 0.2);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

/* 模型选择 - 自定义 select */
.custom-select {
  position: relative;
  width: 100%;
}

.select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-normal);
  gap: 8px;
}

.select-trigger:hover {
  border-color: rgba(0, 212, 255, 0.4);
  background: rgba(255, 255, 255, 0.07);
}

.custom-select.is-open .select-trigger {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
  background: rgba(255, 255, 255, 0.08);
}

.select-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.select-value.placeholder {
  color: var(--text-muted);
  font-weight: 400;
}

.select-arrow {
  width: 16px;
  height: 16px;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.select-arrow.rotated {
  transform: rotate(180deg);
  color: var(--accent-primary);
}

.custom-select.is-open .select-arrow {
  color: var(--accent-primary);
}

/* 下拉面板 */
.select-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 200;
  background: rgba(24, 20, 50, 0.97);
  border: 1px solid rgba(0, 212, 255, 0.25);
  border-radius: var(--radius-md);
  backdrop-filter: blur(30px);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5), 0 0 1px rgba(0, 212, 255, 0.3);
  overflow: hidden;
}

/* 下拉动画 */
.select-dropdown-enter-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.select-dropdown-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.select-dropdown-enter-from {
  opacity: 0;
  transform: translateY(-8px) scale(0.97);
}

.select-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.99);
}

/* 搜索框 */
.select-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
}

.search-icon {
  width: 14px;
  height: 14px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
}

.search-input::placeholder {
  color: var(--text-muted);
}

/* 选项列表 */
.select-options {
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 212, 255, 0.3) transparent;
}

.select-options::-webkit-scrollbar {
  width: 4px;
}

.select-options::-webkit-scrollbar-thumb {
  background: rgba(0, 212, 255, 0.3);
  border-radius: 2px;
}

/* 分组标签 */
.option-group-label {
  padding: 10px 12px 6px;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-primary);
  text-transform: uppercase;
  letter-spacing: 1.5px;
}

/* 选项条目 */
.option-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.option-item:hover {
  background: rgba(0, 212, 255, 0.1);
}

.option-item.active {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.15) 0%, rgba(123, 44, 191, 0.15) 100%);
}

.option-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.option-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.option-item.active .option-name {
  color: var(--accent-primary);
}

.option-desc {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.option-check {
  width: 16px;
  height: 16px;
  color: var(--accent-primary);
  flex-shrink: 0;
  margin-left: 8px;
}

.option-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--text-muted);
}

/* 设置项 */
.setting-item {
  margin-bottom: 18px;
}

.setting-item:last-child {
  margin-bottom: 0;
}

.setting-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-weight: 500;
}

/* 快速提示 */
.quick-tips .tips-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tip-item {
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.tip-item:hover {
  background: rgba(0, 212, 255, 0.08);
  border-color: rgba(0, 212, 255, 0.3);
  color: var(--text-primary);
}
</style>
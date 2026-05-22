<script setup lang="ts">
import { Setting } from '@element-plus/icons-vue'

defineProps<{
  temperature: number
  maxTokens: number
  topK: number
}>()

defineEmits<{
  'update:temperature': [value: number]
  'update:max-tokens': [value: number]
  'update:top-k': [value: number]
}>()
</script>

<template>
  <div class="settings-section">
    <div class="section-header">
      <div class="section-header-main">
        <div class="section-icon">
          <el-icon><Setting /></el-icon>
        </div>
        <div>
          <h2>模型参数</h2>
          <p>调整生成内容的参数</p>
        </div>
      </div>
    </div>

    <div class="settings-form">
      <div class="form-group">
        <div class="form-label">
          <span>Temperature</span>
          <span class="form-value">{{ temperature }}</span>
        </div>
        <el-slider
          :model-value="temperature"
          :min="0"
          :max="2"
          :step="0.1"
          :show-tooltip="false"
          class="custom-slider"
          @update:model-value="$emit('update:temperature', $event)"
        />
        <div class="form-hint">数值越低，回答越确定性；数值越高，回答越有创意</div>
      </div>

      <div class="form-group">
        <div class="form-label">
          <span>Max Tokens</span>
          <span class="form-value">{{ maxTokens }}</span>
        </div>
        <el-input-number
          :model-value="maxTokens"
          :min="256"
          :max="8192"
          :step="256"
          controls-position="right"
          class="form-input"
          @update:model-value="$emit('update:max-tokens', $event)"
        />
        <div class="form-hint">限制生成回答的最大长度</div>
      </div>

      <div class="form-group">
        <div class="form-label">
          <span>Top K</span>
          <span class="form-value">{{ topK }}</span>
        </div>
        <el-input-number
          :model-value="topK"
          :min="1"
          :max="20"
          controls-position="right"
          class="form-input"
          @update:model-value="$emit('update:top-k', $event)"
        />
        <div class="form-hint">检索时返回的相关文档片段数量</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-section {
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 28px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--glass-border);
}

.section-header-main {
  display: flex;
  align-items: center;
  gap: 16px;
}

.section-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.15) 0%, rgba(123, 44, 191, 0.15) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-primary);
  font-size: 22px;
}

.section-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.section-header p {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-label span:first-child {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent-primary);
}

.form-hint {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.form-input {
  width: 100%;
}
</style>
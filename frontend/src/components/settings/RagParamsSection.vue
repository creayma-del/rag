<script setup lang="ts">
import { Files } from '@element-plus/icons-vue'
import type { SystemConfig } from '../../api'

defineProps<{
  systemConfig: SystemConfig
}>()

defineEmits<{
  'update:chunk-size': [value: number]
  'update:chunk-overlap': [value: number]
  'update:embedding-model': [value: string]
  'update:reranker-model': [value: string]
}>()
</script>

<template>
  <div class="settings-section">
    <div class="section-header">
      <div class="section-header-main">
        <div class="section-icon rag">
          <el-icon><Files /></el-icon>
        </div>
        <div>
          <h2>RAG 参数</h2>
          <p>配置向量化和检索参数</p>
        </div>
      </div>
    </div>

    <div class="settings-form">
      <div class="form-group">
        <div class="form-label">
          <span>Chunk Size</span>
          <span class="form-value">{{ systemConfig.chunk_size }}</span>
        </div>
        <el-input-number
          :model-value="systemConfig.chunk_size"
          :min="100"
          :max="4000"
          :step="100"
          controls-position="right"
          class="form-input"
          @update:model-value="$emit('update:chunk-size', $event)"
        />
        <div class="form-hint">文档分块大小，影响检索精度</div>
      </div>

      <div class="form-group">
        <div class="form-label">
          <span>Chunk Overlap</span>
          <span class="form-value">{{ systemConfig.chunk_overlap }}</span>
        </div>
        <el-input-number
          :model-value="systemConfig.chunk_overlap"
          :min="0"
          :max="500"
          :step="10"
          controls-position="right"
          class="form-input"
          @update:model-value="$emit('update:chunk-overlap', $event)"
        />
        <div class="form-hint">分块重叠大小，保持上下文连续性</div>
      </div>

      <div class="form-group">
        <div class="form-label"><span>Embedding Model</span></div>
        <el-input
          :model-value="systemConfig.embedding_model"
          placeholder="向量化模型名称"
          clearable
          @update:model-value="$emit('update:embedding-model', $event)"
        />
        <div class="form-hint">配置文本向量化模型</div>
      </div>

      <div class="form-group">
        <div class="form-label"><span>Reranker Model</span></div>
        <el-input
          :model-value="systemConfig.reranker_model"
          placeholder="重排序模型名称"
          clearable
          @update:model-value="$emit('update:reranker-model', $event)"
        />
        <div class="form-hint">配置 Reranker 重排序模型</div>
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
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.section-icon.rag {
  background: linear-gradient(135deg, rgba(156, 39, 176, 0.15) 0%, rgba(103, 58, 183, 0.15) 100%);
  color: #9c27b0;
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
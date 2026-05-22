<template>
  <div class="settings-section">
    <div class="section-header">
      <div class="section-header-main">
        <div class="section-icon api">
          <el-icon><Key /></el-icon>
        </div>
        <div>
          <h2>API 密钥</h2>
          <p>配置云端模型的 API 密钥</p>
        </div>
      </div>
    </div>

    <el-input
      :model-value="searchText"
      placeholder="搜索 API Key..."
      :prefix-icon="Search"
      clearable
      class="api-key-search"
      @update:model-value="$emit('update:search-text', $event)"
    />

    <el-collapse
      :model-value="activeApiKey"
      accordion
      class="api-collapse"
      @update:model-value="$emit('update:active-api-key', $event)"
    >
      <el-collapse-item
        v-for="model in filteredModels"
        :key="model.name"
        :name="model.name"
      >
        <template #title>
          <div class="collapse-header">
            <span class="collapse-name">{{ model.name }}</span>
            <span class="collapse-model">{{ model.description || model.model }}</span>
            <el-tag
              v-if="hasKey(model.name, apiKeysConfigured)"
              size="small"
              type="success"
              class="collapse-tag"
            >
              已配置
            </el-tag>
            <el-tag
              v-else
              size="small"
              type="info"
              class="collapse-tag"
            >
              未配置
            </el-tag>
          </div>
        </template>
        <div class="collapse-content">
          <div
            v-if="apiKeysMasked[model.name]"
            class="masked-key-hint"
          >
            <el-icon><Lock /></el-icon>
            <span class="masked-key-value">{{ apiKeysMasked[model.name] }}</span>
          </div>
          <el-input
            :model-value="apiKeys[model.name]"
            type="password"
            :placeholder="hasKey(model.name, apiKeysConfigured) ? '输入新密钥以替换' : `输入 ${model.name} API Key`"
            show-password
            class="api-input"
            clearable
            @update:model-value="$emit('update:api-key', model.name, $event)"
            @input="$emit('change')"
          />
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { Key, Search, Lock } from '@element-plus/icons-vue'

interface CloudModel {
  name: string
  description?: string
  model?: string
}

defineProps<{
  filteredModels: CloudModel[]
  apiKeys: Record<string, string>
  apiKeysMasked: Record<string, string>
  apiKeysConfigured: Record<string, boolean>
  activeApiKey: string
  searchText: string
}>()

defineEmits<{
  'update:active-api-key': [value: string]
  'update:search-text': [value: string]
  'update:api-key': [modelName: string, value: string]
  'change': []
}>()

function hasKey(modelName: string, configured: Record<string, boolean>): boolean {
  return !!configured[modelName]
}
</script>
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

.section-icon.api {
  background: linear-gradient(135deg, rgba(0, 245, 147, 0.15) 0%, rgba(0, 196, 133, 0.15) 100%);
  color: var(--accent-tertiary);
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

.api-collapse {
  border: none;
  background: transparent;
  margin-bottom: 16px;
}

.api-key-search {
  margin-bottom: 16px;
}

.api-key-search :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.03) !important;
  box-shadow: none !important;
}

.api-collapse :deep(.el-collapse-item__header) {
  margin-bottom: 6px !important;
}

.api-collapse :deep(.el-collapse-item__header:hover) {
  background: rgba(0, 212, 255, 0.06) !important;
  border-color: rgba(0, 212, 255, 0.2) !important;
}

.api-collapse :deep(.el-collapse-item.is-active .el-collapse-item__header) {
  border-bottom-left-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
  border-color: rgba(0, 212, 255, 0.3) !important;
  background: rgba(0, 212, 255, 0.08) !important;
}

.api-collapse :deep(.el-collapse-item__content) {
  border-radius: 0 0 var(--radius-md) var(--radius-md) !important;
}

.collapse-header {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.collapse-name {
  font-weight: 600;
  color: var(--text-primary);
  min-width: 90px;
}

.collapse-model {
  font-size: 12px;
  color: var(--text-muted);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.collapse-tag {
  flex-shrink: 0;
}

.collapse-content {
  padding: 0;
}

.masked-key-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(0, 245, 147, 0.06);
  border: 1px solid rgba(0, 245, 147, 0.2);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--accent-tertiary);
}

.masked-key-value {
  font-family: monospace;
  letter-spacing: 1px;
}
</style>
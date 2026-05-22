<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'
import type { SystemConfig } from '../../api'

defineProps<{
  systemConfig: SystemConfig
}>()
</script>

<template>
  <div class="settings-section">
    <div class="section-header">
      <div class="section-header-main">
        <div class="section-icon info">
          <el-icon><InfoFilled /></el-icon>
        </div>
        <div>
          <h2>系统信息</h2>
          <p>查看系统配置和状态</p>
        </div>
      </div>
    </div>

    <div class="info-list">
      <div class="info-item">
        <span class="info-label">向量库路径</span>
        <span class="info-value">{{ systemConfig.vector_db_path }}</span>
      </div>
      <div class="info-item">
        <span class="info-label">文档路径</span>
        <span class="info-value">{{ systemConfig.documents_path }}</span>
      </div>
      <div class="info-item">
        <span class="info-label">支持格式</span>
        <span class="info-value">{{ systemConfig.supported_document_extensions?.join(', ') }}</span>
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

.section-icon.info {
  background: linear-gradient(135deg, rgba(33, 150, 243, 0.15) 0%, rgba(21, 101, 192, 0.15) 100%);
  color: #2196f3;
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

.info-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
}

.info-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
}

.info-value {
  font-size: 13px;
  color: var(--text-muted);
  font-family: monospace;
  word-break: break-all;
  text-align: right;
  max-width: 60%;
}
</style>
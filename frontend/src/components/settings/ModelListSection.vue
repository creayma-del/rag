<script setup lang="ts">
import { Monitor, DataLine, TrendCharts, Cpu, Check } from '@element-plus/icons-vue'

interface CloudModel {
  name: string
  description?: string
  model?: string
}

interface LocalModel {
  name: string
  description?: string
  model?: string
}

defineProps<{
  cloudModels: CloudModel[]
  localModels: LocalModel[]
  saving: boolean
}>()

defineEmits<{
  save: []
}>()
</script>

<template>
  <div class="settings-section full-width">
    <div class="section-header">
      <div class="section-header-main">
        <div class="section-icon models-icon">
          <el-icon><Monitor /></el-icon>
        </div>
        <div>
          <h2>可用模型</h2>
          <p>查看所有支持的模型列表</p>
        </div>
      </div>
      <div class="section-actions">
        <el-button
          type="primary"
          :loading="saving"
          class="save-all-btn"
          @click="$emit('save')"
        >
          <el-icon><Check /></el-icon>
          保存全部配置
        </el-button>
      </div>
    </div>

    <div class="models-grid">
      <div class="model-category">
        <div class="category-title">
          <el-icon><DataLine /></el-icon>
          <span>云端模型</span>
        </div>
        <div class="model-list">
          <div v-for="model in cloudModels" :key="model.name" class="model-item">
            <div class="model-icon">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="model-details">
              <div class="model-name">{{ model.name.toUpperCase() }}</div>
              <div class="model-desc">{{ model.description || model.model }}</div>
            </div>
            <el-tag size="small" type="info">云端</el-tag>
          </div>
        </div>
      </div>

      <div class="model-category">
        <div class="category-title">
          <el-icon><Cpu /></el-icon>
          <span>本地模型</span>
        </div>
        <div class="model-list">
          <div v-for="model in localModels" :key="model.name" class="model-item">
            <div class="model-icon local">
              <el-icon><Cpu /></el-icon>
            </div>
            <div class="model-details">
              <div class="model-name">{{ model.name }}</div>
              <div class="model-desc">{{ model.description || model.model }}</div>
            </div>
            <el-tag size="small" type="success">本地</el-tag>
          </div>
        </div>
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

.settings-section.full-width {
  grid-column: 1 / -1;
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

.section-icon.models-icon {
  background: linear-gradient(135deg, rgba(255, 217, 61, 0.15) 0%, rgba(255, 196, 0, 0.15) 100%);
  color: var(--accent-warning);
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

.section-actions {
  display: flex;
  gap: 12px;
}

.save-all-btn {
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%) !important;
  border: none !important;
  color: white !important;
  border-radius: var(--radius-md) !important;
  padding: 10px 24px !important;
  font-weight: 600 !important;
  gap: 8px !important;
  box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3) !important;
  transition: all var(--transition-normal) !important;
}

.save-all-btn:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 25px rgba(0, 212, 255, 0.4) !important;
}

.models-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.model-category {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.category-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 2px;
  padding: 8px 0;
}

.category-title .el-icon {
  color: var(--accent-primary);
  font-size: 18px;
}

.model-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.model-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.02) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
}

.model-item::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent-primary), transparent);
  opacity: 0;
  transition: opacity var(--transition-normal);
}

.model-item:hover {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.08) 0%, rgba(123, 44, 191, 0.08) 100%);
  border-color: rgba(0, 212, 255, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

.model-item:hover::before { opacity: 1; }

.model-icon {
  width: 48px; height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.15) 0%, rgba(123, 44, 191, 0.15) 100%);
  display: flex; align-items: center; justify-content: center;
  color: var(--accent-primary);
  font-size: 22px; flex-shrink: 0;
  border: 1px solid rgba(0, 212, 255, 0.2);
  box-shadow: 0 4px 15px rgba(0, 212, 255, 0.1);
}

.model-icon.local {
  background: linear-gradient(135deg, rgba(0, 245, 147, 0.15) 0%, rgba(0, 196, 133, 0.15) 100%);
  color: var(--accent-tertiary);
  border-color: rgba(0, 245, 147, 0.2);
  box-shadow: 0 4px 15px rgba(0, 245, 147, 0.1);
}

.model-details {
  flex: 1;
  display: flex; flex-direction: column; gap: 6px;
}

.model-name {
  font-size: 15px; font-weight: 700;
  color: var(--text-primary);
  text-transform: capitalize;
  letter-spacing: 0.3px;
}

.model-desc {
  font-size: 12px; color: var(--text-secondary);
  line-height: 1.5;
}

@media (max-width: 900px) {
  .models-grid { grid-template-columns: 1fr; }
}
</style>
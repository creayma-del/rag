<template>
  <div class="settings-page">
    <div class="page-header">
      <h1>系统设置</h1>
      <p>配置模型参数和 API 密钥</p>
    </div>

    <div class="settings-grid">
      <RagParamsSection
        :system-config="systemConfig"
        @update:chunk-size="systemConfig.chunk_size = $event; markDirty()"
        @update:chunk-overlap="systemConfig.chunk_overlap = $event; markDirty()"
        @update:embedding-model="systemConfig.embedding_model = $event; markDirty()"
        @update:reranker-model="systemConfig.reranker_model = $event; markDirty()"
      />
      <ModelParamsSection
        :temperature="settings.temperature"
        :max-tokens="settings.maxTokens"
        :top-k="settings.topK"
        @update:temperature="settings.temperature = $event"
        @update:max-tokens="settings.maxTokens = $event"
        @update:top-k="settings.topK = $event"
      />
      <ApiKeysSection
        :filtered-models="filteredCloudModels"
        :api-keys="apiKeys"
        :api-keys-masked="apiKeysMasked"
        :api-keys-configured="apiKeysConfigured"
        :active-api-key="activeApiKey"
        :search-text="apiKeySearch"
        @update:active-api-key="activeApiKey = $event"
        @update:search-text="apiKeySearch = $event"
        @change="markDirty"
      />
      <SystemInfoSection :system-config="systemConfig" />
      <ModelListSection
        :cloud-models="models.cloud_models"
        :local-models="models.local_models"
        :saving="saving"
        @save="saveAllSettings"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsForm } from '../composables/useSettingsForm'
import RagParamsSection from '../components/settings/RagParamsSection.vue'
import ModelParamsSection from '../components/settings/ModelParamsSection.vue'
import ApiKeysSection from '../components/settings/ApiKeysSection.vue'
import SystemInfoSection from '../components/settings/SystemInfoSection.vue'
import ModelListSection from '../components/settings/ModelListSection.vue'

const {
  settings,
  apiKeys,
  apiKeysMasked,
  apiKeysConfigured,
  models,
  saving,
  activeApiKey,
  apiKeySearch,
  systemConfig,
  filteredCloudModels,
  markDirty,
  loadModels,
  loadApiKeyStatus,
  loadSystemConfig,
  saveAllSettings,
} = useSettingsForm()

onMounted(() => {
  loadModels()
  loadApiKeyStatus()
  loadSystemConfig()
})
</script>

<style scoped>
.settings-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding-bottom: 20px;
}

.page-header {
  margin-bottom: 28px;
}

.page-header h1 {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 6px 0;
}

.page-header p {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
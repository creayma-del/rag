import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import router from '../router'
import type { SystemConfig } from '../api'

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

export interface ModelsData {
  cloud_models: CloudModel[]
  local_models: LocalModel[]
}

export function useSettingsForm() {
  const settings = useSettingsStore()

  // ---- State ----
  const apiKeys = ref<Record<string, string>>({})
  const apiKeysMasked = ref<Record<string, string>>({})
  const apiKeysConfigured = ref<Record<string, boolean>>({})
  const models = ref<ModelsData>({ cloud_models: [], local_models: [] })
  const saving = ref(false)
  const activeApiKey = ref('')
  const apiKeySearch = ref('')
  const hasUnsavedChanges = ref(false)
  const initialRagConfig = ref({ chunk_size: 0, chunk_overlap: 0, chunk_strategy: 'semantic', semantic_breakpoint_type: 'percentile', semantic_breakpoint_amount: 75, semantic_min_chunk_size: 100, embedding_model: '', reranker_model: '', use_reranker: false })
  const systemConfig = ref<SystemConfig>({
    chunk_size: 500,
    chunk_overlap: 50,
    chunk_strategy: 'semantic',
    semantic_breakpoint_type: 'percentile',
    semantic_breakpoint_amount: 75,
    semantic_min_chunk_size: 100,
    embedding_model: '',
    embedding_dimension: null,
    reranker_model: '',
    use_reranker: false,
    default_model: '',
    max_tokens: 4096,
    temperature: 0.1,
    top_k: 5,
    reranker_top_n: 3,
    vector_db_path: '',
    documents_path: '',
    supported_document_extensions: [],
  })

  const cloudModels = computed(() => models.value.cloud_models || [])

  const filteredCloudModels = computed(() => {
    const query = apiKeySearch.value.toLowerCase().trim()
    if (!query) return cloudModels.value
    return cloudModels.value.filter(
      m => m.name.toLowerCase().includes(query) || (m.description || '').toLowerCase().includes(query)
    )
  })

  function hasKey(modelName: string): boolean {
    return !!apiKeysConfigured.value[modelName]
  }

  function markDirty(): void {
    hasUnsavedChanges.value = true
  }

  // ---- Data Loading ----
  async function loadModels(): Promise<void> {
    try {
      const res = await api.getModels()
      models.value = res.data as ModelsData
    } catch {
      ElMessage.error('加载模型列表失败')
    }
  }

  async function loadApiKeyStatus(): Promise<void> {
    try {
      const res = await api.getApiKeyStatus()
      const keys = res.data.keys as Record<string, { configured: boolean; masked: string }>
      for (const [name, info] of Object.entries(keys)) {
        apiKeysConfigured.value[name] = info.configured
        apiKeysMasked.value[name] = info.masked
      }
    } catch {
      // 非关键接口，静默失败
    }
  }

  async function loadSystemConfig(): Promise<void> {
    try {
      const res = await api.getSystemConfig()
      systemConfig.value = res.data as SystemConfig
      initialRagConfig.value = {
        chunk_size: systemConfig.value.chunk_size,
        chunk_overlap: systemConfig.value.chunk_overlap,
        chunk_strategy: systemConfig.value.chunk_strategy,
        semantic_breakpoint_type: systemConfig.value.semantic_breakpoint_type,
        semantic_breakpoint_amount: systemConfig.value.semantic_breakpoint_amount,
        semantic_min_chunk_size: systemConfig.value.semantic_min_chunk_size,
        embedding_model: systemConfig.value.embedding_model,
        reranker_model: systemConfig.value.reranker_model,
        use_reranker: systemConfig.value.use_reranker,
      }
    } catch {
      ElMessage.error('加载系统配置失败')
    }
  }

  // ---- Save ----
  async function saveAllSettings(): Promise<void> {
    if (systemConfig.value.chunk_overlap >= systemConfig.value.chunk_size) {
      ElMessage.warning('Chunk Overlap 不能大于或等于 Chunk Size，请调整后重试')
      return
    }

    saving.value = true
    try {
      let saved = false

      for (const model of cloudModels.value) {
        const key = apiKeys.value[model.name]
        if (key && key.trim()) {
          const payload: { model: string; api_key: string; secret_key?: string } = { model: model.name, api_key: key.trim() }
          // 文心一言模型需要同时发送 secret_key
          if (model.name === 'wenxin' && apiKeys.value['wenxin__secret']?.trim()) {
            payload.secret_key = apiKeys.value['wenxin__secret'].trim()
          }
          await api.updateConfig(payload)
          saved = true
          apiKeys.value[model.name] = ''
          if (model.name === 'wenxin') {
            apiKeys.value['wenxin__secret'] = ''
          }
        }
      }

      await api.updateSystemConfig({
        chunk_size: systemConfig.value.chunk_size,
        chunk_overlap: systemConfig.value.chunk_overlap,
        chunk_strategy: systemConfig.value.chunk_strategy,
        semantic_breakpoint_type: systemConfig.value.semantic_breakpoint_type,
        semantic_breakpoint_amount: systemConfig.value.semantic_breakpoint_amount,
        semantic_min_chunk_size: systemConfig.value.semantic_min_chunk_size,
        embedding_model: systemConfig.value.embedding_model,
        reranker_model: systemConfig.value.reranker_model,
        use_reranker: systemConfig.value.use_reranker,
      })
      saved = true

      if (saved) {
        hasUnsavedChanges.value = false
        await loadApiKeyStatus()

        const ragChanged =
          systemConfig.value.chunk_size !== initialRagConfig.value.chunk_size ||
          systemConfig.value.chunk_overlap !== initialRagConfig.value.chunk_overlap ||
          systemConfig.value.chunk_strategy !== initialRagConfig.value.chunk_strategy ||
          systemConfig.value.semantic_breakpoint_type !== initialRagConfig.value.semantic_breakpoint_type ||
          systemConfig.value.semantic_breakpoint_amount !== initialRagConfig.value.semantic_breakpoint_amount ||
          systemConfig.value.semantic_min_chunk_size !== initialRagConfig.value.semantic_min_chunk_size ||
          systemConfig.value.embedding_model !== initialRagConfig.value.embedding_model ||
          systemConfig.value.reranker_model !== initialRagConfig.value.reranker_model ||
          systemConfig.value.use_reranker !== initialRagConfig.value.use_reranker

        if (ragChanged) {
          initialRagConfig.value = {
            chunk_size: systemConfig.value.chunk_size,
            chunk_overlap: systemConfig.value.chunk_overlap,
            chunk_strategy: systemConfig.value.chunk_strategy,
            semantic_breakpoint_type: systemConfig.value.semantic_breakpoint_type,
            semantic_breakpoint_amount: systemConfig.value.semantic_breakpoint_amount,
            semantic_min_chunk_size: systemConfig.value.semantic_min_chunk_size,
            embedding_model: systemConfig.value.embedding_model,
            reranker_model: systemConfig.value.reranker_model,
            use_reranker: systemConfig.value.use_reranker,
          }
          await ElMessageBox.confirm(
            'RAG 核心参数（Chunk Size、Overlap、分块策略、Embedding/Reranker 模型）已修改。\n\n' +
            '需要重建知识库才能使新参数生效。是否现在前往文档管理页重建？',
            '参数变更提示',
            { confirmButtonText: '前往重建', cancelButtonText: '稍后', type: 'warning' }
          ).then(() => {
            router.push('/documents')
          }).catch(() => {
            ElMessage.info('配置已保存。请在文档管理页面重新构建知识库以应用新参数。')
          })
        } else {
          ElMessage.success('配置保存成功！')
        }
      } else {
        ElMessage.info('没有需要保存的配置')
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      ElMessage.error('保存失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      saving.value = false
    }
  }

  // ---- Page unload guard ----
  function beforeUnloadHandler(event: BeforeUnloadEvent): void {
    if (hasUnsavedChanges.value) {
      event.preventDefault()
      event.returnValue = ''
    }
  }

  onMounted(() => {
    window.addEventListener('beforeunload', beforeUnloadHandler)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', beforeUnloadHandler)
  })

  return {
    // state
    settings,
    apiKeys,
    apiKeysMasked,
    apiKeysConfigured,
    models,
    saving,
    activeApiKey,
    apiKeySearch,
    hasUnsavedChanges,
    systemConfig,
    // computed
    cloudModels,
    filteredCloudModels,
    // actions
    hasKey,
    markDirty,
    loadModels,
    loadApiKeyStatus,
    loadSystemConfig,
    saveAllSettings,
  }
}
<template>
  <div class="documents-page">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h1>文档管理</h1>
        <p>上传并管理您的知识库文档</p>
      </div>
      <div class="header-actions">
        <el-button
          class="btn-secondary"
          :loading="preloading"
          @click="preloadModels"
        >
          <el-icon><Download /></el-icon>
          预加载模型
        </el-button>
        <el-button
          class="btn-secondary"
          :loading="preloadingAll"
          :disabled="preloading"
          @click="preloadAllLocalModels"
        >
          <el-icon><Download /></el-icon>
          预加载所有本地模型
        </el-button>
        <UploadDropZone
          :is-drag-over="isDragOver"
          :accepted-types="acceptedUploadTypes"
          :uploading-file="uploadingFile"
          :upload-progress="uploadProgress"
          @files-selected="onFilesSelected"
          @drag-over-change="isDragOver = $event"
        />
      </div>
    </div>

    <!-- Content Grid -->
    <div class="content-grid">
      <DocumentList
        :documents="filteredDocuments"
        :loading="loadingDocs"
        :search-text="docSearch"
        :doc-count-label="String(filteredDocuments.length)"
        :total-size-label="totalSize"
        @update:search-text="docSearch = $event"
        @preview="docs.previewDocument"
        @delete="handleDeleteDoc"
      />
      <KnowledgeBaseStatus
        :exists="vectorStoreExists"
        :stale="vectorStoreStale"
        :building="building"
        :document-count="documents.length"
        :supported-formats="supportedFormatLabels"
        @build="buildVectorStore"
      />
    </div>

    <!-- Preview Dialog -->
    <DocumentPreviewDialog
      :visible="previewVisible"
      :file-name="previewFileName"
      :loading="previewLoading"
      :error="previewError"
      :message="previewMessage"
      :content="previewContent"
      :line-count="previewLineCount"
      :file-size="previewFileSize"
      @update:visible="previewVisible = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useDocuments, useVectorStore } from '../composables/useDocuments'
import UploadDropZone from '../components/documents/UploadDropZone.vue'
import DocumentList from '../components/documents/DocumentList.vue'
import KnowledgeBaseStatus from '../components/documents/KnowledgeBaseStatus.vue'
import DocumentPreviewDialog from '../components/documents/DocumentPreviewDialog.vue'

interface LocalModel {
  name: string
  description?: string
}

// ---- Composables ----
const docs = useDocuments()
const vs = useVectorStore()

const {
  documents, loadingDocs, uploadingFile, uploadProgress, docSearch,
  isDragOver, filteredDocuments, uploadExtensions,
  previewVisible, previewLoading, previewFileName, previewContent,
  previewFileSize, previewLineCount, previewError, previewMessage,
} = docs

const {
  building, preloading, preloadingAll, vectorStoreExists, vectorStoreStale,
} = vs

const localModels = ref<LocalModel[]>([])

// ---- Computed ----
const totalSize = computed(() => {
  const bytes = documents.value.reduce((acc, doc) => acc + doc.size, 0)
  return formatSize(bytes)
})

const acceptedUploadTypes = computed(() => uploadExtensions.join(','))

const supportedFormatLabels = 'TXT, MD, MARKDOWN, PDF, DOCX, CSV, JSON, HTML, XML, YAML, ZIP'

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// ---- Upload ----
function onFilesSelected(files: FileList): void {
  docs.uploadFiles(files)
}

// ---- Delete ----
async function handleDeleteDoc(name: string): Promise<void> {
  await docs.deleteDocument(name)
  await vs.checkStatus()
}

// ---- Build ----
async function buildVectorStore(): Promise<void> {
  await vs.build(docs.documents.value.length)
}

// ---- Model Preloading ----
async function loadLocalModels(): Promise<void> {
  try {
    const res = await api.getModels()
    localModels.value = (res.data.local_models as LocalModel[]) ?? []
  } catch { /* ignore */ }
}

async function preloadModels(): Promise<void> {
  preloading.value = true
  try {
    ElMessage.info('正在启动模型预加载...')
    const res = await api.preloadModels()
    const status = res.data.status as string
    if (status === 'ready') {
      ElMessage.success('默认模型已在缓存中，无需重复加载')
    } else if (status === 'started' || status === 'loading') {
      ElMessage.success('默认模型后台预加载已启动，可在对话中直接使用')
    } else {
      ElMessage.warning('模型预加载状态未知: ' + status)
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    ElMessage.error('模型预加载失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    preloading.value = false
  }
}

async function preloadAllLocalModels(): Promise<void> {
  preloadingAll.value = true
  try {
    if (localModels.value.length === 0) {
      ElMessage.warning('没有可用的本地模型')
      return
    }

    let successCount = 0
    let failCount = 0
    for (let i = 0; i < localModels.value.length; i++) {
      const model = localModels.value[i]
      ElMessage.info(`[${i + 1}/${localModels.value.length}] 启动预加载: ${model.name}`)

      try {
        const preloadRes = await api.preloadModelRuntime({ model: model.name, use_reranker: false })
        if (preloadRes.data.status === 'ready') {
          successCount++
          ElMessage.success(`[${i + 1}/${localModels.value.length}] ${model.name} 已就绪（缓存命中）`)
          continue
        }

        const startTime = Date.now()
        const maxWaitMs = 30 * 60 * 1000
        let loaded = false

        while (Date.now() - startTime < maxWaitMs) {
          await new Promise(resolve => setTimeout(resolve, 3000))
          const statusRes = await api.getPreloadStatus(model.name)
          const { state, error } = statusRes.data as { state: string; error?: string }
          if (state === 'ready') {
            successCount++
            ElMessage.success(`[${i + 1}/${localModels.value.length}] ${model.name} 预加载完成`)
            loaded = true
            break
          }
          if (state === 'failed') throw new Error(error || '加载失败')
        }
        if (!loaded) throw new Error('加载超时，请检查网络或设置 HF_ENDPOINT 镜像')
      } catch (e: unknown) {
        failCount++
        const err = e as { response?: { data?: { detail?: string } }; message?: string }
        ElMessage.error(`[${i + 1}/${localModels.value.length}] ${model.name} 预加载失败: ${err.response?.data?.detail || (e instanceof Error ? e.message : '')}`)
      }
    }

    if (failCount === 0) {
      ElMessage.success(`全部 ${successCount} 个本地模型预加载完成！`)
    } else {
      ElMessage.warning(`预加载完成: ${successCount} 成功, ${failCount} 失败`)
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    ElMessage.error('获取模型列表失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    preloadingAll.value = false
  }
}

// ---- Lifecycle ----
onMounted(async () => {
  docs.loadDocuments()
  vs.checkStatus()
  loadLocalModels()
})
</script>

<style scoped>
.documents-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding-bottom: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
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

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.08) !important;
  border: 1px solid var(--glass-border) !important;
  color: var(--text-primary) !important;
  border-radius: var(--radius-md) !important;
  padding: 0 20px !important;
  font-weight: 500 !important;
  transition: all var(--transition-normal) !important;
}

.btn-secondary:hover {
  background: rgba(0, 212, 255, 0.1) !important;
  border-color: var(--accent-primary) !important;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 20px;
}

@media (max-width: 1100px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
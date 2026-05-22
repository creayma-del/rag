import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

export interface DocItem {
  name: string
  size: number
}

export function useDocuments() {
  const documents = ref<DocItem[]>([])
  const loadingDocs = ref(false)
  const uploadingFile = ref<string | null>(null)
  const uploadProgress = ref(0)
  const docSearch = ref('')
  const isDragOver = ref(false)

  // 预览状态
  const previewVisible = ref(false)
  const previewLoading = ref(false)
  const previewFileName = ref('')
  const previewContent = ref<string | null>(null)
  const previewFileSize = ref(0)
  const previewLineCount = ref(0)
  const previewError = ref('')
  const previewMessage = ref('')

  const uploadExtensions: string[] = [
    '.txt', '.md', '.markdown', '.pdf', '.docx', '.csv',
    '.json', '.html', '.htm', '.xml', '.yml', '.yaml', '.zip',
  ]

  const filteredDocuments = computed(() => {
    const query = docSearch.value.toLowerCase().trim()
    if (!query) return documents.value
    return documents.value.filter((d) => d.name.toLowerCase().includes(query))
  })

  async function loadDocuments(): Promise<void> {
    loadingDocs.value = true
    try {
      const res = await api.listDocuments()
      documents.value = (res.data.documents as DocItem[]) ?? []
    } catch {
      documents.value = []
    } finally {
      loadingDocs.value = false
    }
  }

  async function uploadFile(file: File): Promise<void> {
    uploadingFile.value = file.name
    uploadProgress.value = 0
    try {
      await api.uploadDocument(file, (progressEvent) => {
        if (progressEvent.total) uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      })
      ElMessage.success(`文件 "${file.name}" 上传成功`)
      await loadDocuments()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      ElMessage.error('上传失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      uploadingFile.value = null
      uploadProgress.value = 0
    }
  }

  async function uploadFiles(files: FileList | File[]): Promise<void> {
    for (const file of files) {
      await uploadFile(file)
    }
  }

  async function deleteDocument(name: string): Promise<void> {
    try {
      await ElMessageBox.confirm(`确定删除文档 "${name}"？`, '删除确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
      const res = await api.deleteDocument(name)
      documents.value = documents.value.filter((d) => d.name !== name)
      const data = res.data as { warning?: string }
      if (data.warning) {
        ElMessage.warning(`已删除 "${name}"，但${data.warning}，建议重新构建知识库`)
      } else {
        ElMessage.success(`已删除 "${name}"，向量库已同步更新`)
      }
    } catch {
      // 取消
    }
  }

  async function previewDocument(name: string): Promise<void> {
    previewVisible.value = true
    previewFileName.value = name
    previewLoading.value = true
    previewContent.value = null
    previewError.value = ''
    previewMessage.value = ''
    try {
      const res = await api.previewDocument(name)
      const data = res.data as {
        type: string; content: string | null; size: number;
        lines?: number; message?: string;
      }
      if (data.content !== null) {
        previewContent.value = data.content
        previewFileSize.value = data.size
        previewLineCount.value = data.lines ?? 0
      } else {
        previewFileSize.value = data.size
        previewMessage.value = data.message ?? '不支持在线预览'
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      previewError.value = err.response?.data?.detail || '预览失败'
    } finally {
      previewLoading.value = false
    }
  }

  function closePreview(): void {
    previewVisible.value = false
    previewContent.value = null
  }

  function formatSize(bytes: number): string {
    if (!bytes) return '0 B'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return {
    documents, loadingDocs, uploadingFile, uploadProgress, docSearch,
    isDragOver, filteredDocuments, uploadExtensions,
    previewVisible, previewLoading, previewFileName, previewContent,
    previewFileSize, previewLineCount, previewError, previewMessage,
    loadDocuments, uploadFile, uploadFiles, deleteDocument, previewDocument,
    closePreview, formatSize,
  }
}

export function useVectorStore() {
  const building = ref(false)
  const preloading = ref(false)
  const preloadingAll = ref(false)
  const vectorStoreExists = ref(false)
  const vectorStoreStale = ref(false)

  async function checkStatus(): Promise<void> {
    try {
      const res = await api.getVectorStoreStatus()
      vectorStoreExists.value = res.data.exists as boolean
      vectorStoreStale.value = Boolean(res.data.stale)
    } catch {
      // 忽略
    }
  }

  async function build(docsCount: number): Promise<void> {
    if (docsCount === 0) {
      ElMessage.warning('请先上传文档')
      return
    }
    building.value = true
    try {
      const res = await api.buildVectorStore()
      ElMessage.success(`构建成功！处理了 ${res.data.documents_count} 个文档，${res.data.chunks_count} 个块`)
      vectorStoreExists.value = true
      vectorStoreStale.value = false
      // 通知其他页面向量库状态已变更
      window.dispatchEvent(new CustomEvent('vectorstore:changed', { detail: { exists: true, stale: false } }))
    } catch (e: unknown) {
      const err = e as { response?: { status?: number; data?: { detail?: string } } }
      if (err.response?.status === 409) {
        ElMessage.warning(err.response.data?.detail || '构建正在进行中')
        return
      }
      ElMessage.error(err.response?.data?.detail || '构建失败')
      vectorStoreStale.value = true
      window.dispatchEvent(new CustomEvent('vectorstore:changed', { detail: { exists: vectorStoreExists.value, stale: true } }))
    } finally {
      building.value = false
    }
  }

  async function preloadModel(modelName: string): Promise<void> {
    if (!modelName) return
    preloading.value = true
    try {
      await api.preloadModelRuntime({ model: modelName, use_reranker: false })
      ElMessage.success(`模型 "${modelName}" 预热成功`)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      ElMessage.error('预热失败: ' + (err.response?.data?.detail || '未知错误'))
    } finally {
      preloading.value = false
    }
  }

  async function preloadAll(localModels: { name: string }[]): Promise<void> {
    if (!localModels.length) {
      ElMessage.warning('没有可用的本地模型')
      return
    }
    preloadingAll.value = true
    let success = 0
    for (const m of localModels) {
      try {
        await api.preloadModelRuntime({ model: m.name, use_reranker: false })
        success++
      } catch {
        // 跳过失败的
      }
    }
    ElMessage.success(`预热完成：${success}/${localModels.length} 个模型成功`)
    preloadingAll.value = false
  }

  return {
    building, preloading, preloadingAll, vectorStoreExists, vectorStoreStale,
    checkStatus, build, preloadModel, preloadAll,
  }
}
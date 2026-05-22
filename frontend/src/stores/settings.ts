import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

interface SettingsState {
  selectedModel: string
  temperature: number
  maxTokens: number
  topK: number
  useReranker: boolean
  rerankerTopN: number
}

const STORAGE_KEY = 'rag-settings'

function loadFromStorage(): SettingsState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return JSON.parse(raw) as SettingsState
    }
  } catch {
    // ignore corrupt data
  }
  return null
}

function saveToStorage(state: SettingsState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // storage full or unavailable
  }
}

export const useSettingsStore = defineStore('settings', () => {
  const saved = loadFromStorage()

  const selectedModel = ref<string>(saved?.selectedModel ?? 'local')
  const temperature = ref<number>(saved?.temperature ?? 0.1)
  const maxTokens = ref<number>(saved?.maxTokens ?? 4096)
  const topK = ref<number>(saved?.topK ?? 5)
  const useReranker = ref<boolean>(saved?.useReranker ?? false)
  const rerankerTopN = ref<number>(saved?.rerankerTopN ?? 3)

  // 自动持久化（不再包含 API Key）
  watch(
    [selectedModel, temperature, maxTokens, topK, useReranker, rerankerTopN],
    () => {
      saveToStorage({
        selectedModel: selectedModel.value,
        temperature: temperature.value,
        maxTokens: maxTokens.value,
        topK: topK.value,
        useReranker: useReranker.value,
        rerankerTopN: rerankerTopN.value,
      })
    },
    { deep: true }
  )

  function setSelectedModel(model: string): void {
    selectedModel.value = model
  }

  function setTemperature(value: number): void {
    temperature.value = value
  }

  function setMaxTokens(value: number): void {
    maxTokens.value = value
  }

  function setTopK(value: number): void {
    topK.value = value
  }

  return {
    selectedModel,
    temperature,
    maxTokens,
    topK,
    useReranker,
    rerankerTopN,
    setSelectedModel,
    setTemperature,
    setMaxTokens,
    setTopK,
  }
})
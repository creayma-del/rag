import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import type { SessionItem } from '../types/chat'

export function useSessions() {
  const sessions = ref<SessionItem[]>([])
  const loadingSessions = ref(false)
  const currentSessionId = ref<string | null>(null)
  const sessionsSearch = ref('')
  const sessionsPageSize = 20
  const sessionsDisplayCount = ref(sessionsPageSize)

  const filteredSessions = computed(() => {
    const query = sessionsSearch.value.toLowerCase().trim()
    const slice = query
      ? sessions.value.filter((s) => s.title.toLowerCase().includes(query))
      : sessions.value
    return slice.slice(0, sessionsDisplayCount.value)
  })

  function loadMoreSessions(): void {
    sessionsDisplayCount.value += sessionsPageSize
  }

  async function loadSessions(): Promise<void> {
    loadingSessions.value = true
    try {
      const res = await api.listSessions()
      sessions.value = (res.data.sessions as SessionItem[] | undefined) ?? []
      // 刷新页面后恢复最近会话：如果当前没有选中会话且列表非空，自动选中最近的
      if (!currentSessionId.value && sessions.value.length > 0) {
        currentSessionId.value = sessions.value[0].session_id
      }
    } catch {
      sessions.value = []
    } finally {
      loadingSessions.value = false
    }
  }

  async function createNewSession(messagesCount: number): Promise<void> {
    if (messagesCount > 0 && currentSessionId.value) {
      try {
        await ElMessageBox.confirm(
          '创建新对话后当前对话将被保存，确定继续？',
          '新建对话',
          { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
    }

    try {
      const res = await api.createSession()
      currentSessionId.value = res.data.session_id as string
      await loadSessions()
      ElMessage.success('已创建新对话')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      ElMessage.error('创建新对话失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  async function loadSession(sessionId: string, force: boolean = false): Promise<Record<string, unknown> | null> {
    if (!force && sessionId === currentSessionId.value) return null
    try {
      const res = await api.getSession(sessionId)
      currentSessionId.value = sessionId
      return res.data as Record<string, unknown>
    } catch {
      ElMessage.error('加载对话历史失败')
      return null
    }
  }

  async function deleteSession(sessionId: string): Promise<{ wasCurrent: boolean } | null> {
    try {
      await api.deleteSession(sessionId)
      const wasCurrent = currentSessionId.value === sessionId
      if (wasCurrent) {
        currentSessionId.value = null
      }
      sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
      ElMessage.success('已删除对话')
      return { wasCurrent }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      ElMessage.error(err.response?.data?.detail || '删除失败')
      return null
    }
  }

  async function renameSession(sessionId: string, currentTitle: string): Promise<void> {
    try {
      const { value: newTitle } = await ElMessageBox.prompt('请输入新标题', '重命名', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: currentTitle,
      })
      if (newTitle) {
        await api.updateSessionTitle(sessionId, newTitle.trim())
        const session = sessions.value.find((s) => s.session_id === sessionId)
        if (session) session.title = newTitle.trim()
        ElMessage.success('已重命名')
      }
    } catch {
      // 取消
    }
  }

  return {
    sessions,
    loadingSessions,
    currentSessionId,
    sessionsSearch,
    sessionsDisplayCount,
    filteredSessions,
    loadSessions,
    createNewSession,
    loadSession,
    deleteSession,
    renameSession,
    loadMoreSessions,
  }
}
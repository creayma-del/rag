<template>
  <div :class="['session-sidebar', { 'mobile-open': modelValue }]">
    <div class="sidebar-header">
      <h3>对话历史</h3>
      <el-button
        type="primary"
        size="small"
        :icon="Plus"
        class="new-session-btn"
        @click="$emit('createNewSession')"
      >
        新对话
      </el-button>
    </div>

    <div class="session-search">
      <el-input
        :model-value="searchText"
        placeholder="搜索对话..."
        size="small"
        clearable
        :prefix-icon="Search"
        @update:model-value="$emit('update:searchText', $event)"
      />
    </div>

    <div class="session-list">
      <!-- 骨架屏 -->
      <div
        v-if="loading"
        class="session-skeleton-list"
      >
        <div
          v-for="i in 4"
          :key="'ssk' + i"
          class="session-skeleton-item"
        >
          <div class="skeleton-avatar" />
          <div class="skeleton-text">
            <div class="skeleton-line-title" />
            <div class="skeleton-line-meta" />
          </div>
        </div>
      </div>

      <div
        v-for="session in filteredSessions"
        :key="session.session_id"
        :class="['session-item', { active: currentSessionId === session.session_id }]"
        @click="$emit('selectSession', session.session_id)"
      >
        <div class="session-icon">
          <el-icon><ChatDotRound /></el-icon>
        </div>
        <div class="session-info">
          <div class="session-title">
            {{ session.title }}
          </div>
          <div class="session-meta">
            {{ formatDate(session.updated_at) }} · {{ session.message_count }} 条消息
          </div>
        </div>
        <div
          class="session-actions"
          @click.stop
        >
          <el-dropdown trigger="click">
            <el-button
              link
              size="small"
              :icon="MoreFilled"
            />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  :icon="Edit"
                  @click="$emit('renameSession', session)"
                >
                  重命名
                </el-dropdown-item>
                <el-dropdown-item
                  :icon="Delete"
                  divided
                  @click="confirmDelete(session.session_id)"
                >
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <div
        v-if="filteredSessions.length === 0 && !loading"
        class="empty-sessions"
      >
        <el-icon><Document /></el-icon>
        <p v-if="allSessions.length === 0">
          暂无对话历史
        </p>
        <p v-else>
          未找到匹配的对话
        </p>
        <p
          v-if="allSessions.length === 0"
          class="hint"
        >
          开始新对话后会自动保存
        </p>
      </div>

      <div
        v-if="filteredSessions.length > 0 && !searchText && allSessions.length > displayCount"
        class="load-more-wrap"
      >
        <el-button
          size="small"
          text
          @click="$emit('loadMoreSessions')"
        >
          加载更多（{{ allSessions.length - displayCount }} 条）
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Plus, ChatDotRound, MoreFilled, Edit, Delete, Document, Search,
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import type { SessionItem } from '../../types/chat'

defineProps<{
  modelValue: boolean
  allSessions: SessionItem[]
  filteredSessions: SessionItem[]
  loading: boolean
  searchText: string
  currentSessionId: string | null
  displayCount: number
}>()

const emit = defineEmits<{
  'update:searchText': [value: string]
  createNewSession: []
  selectSession: [sessionId: string]
  renameSession: [session: SessionItem]
  deleteSession: [sessionId: string]
  loadMoreSessions: []
}>()

async function confirmDelete(sessionId: string): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要删除该对话吗？删除后不可恢复。', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    emit('deleteSession', sessionId)
  } catch {
    // 用户取消
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  if (diffMs < 60_000) return '刚刚'
  if (diffMs < 3_600_000) return Math.floor(diffMs / 60_000) + ' 分钟前'
  if (diffMs < 86_400_000) return Math.floor(diffMs / 3_600_000) + ' 小时前'
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
/* 根元素（宽/背景/圆角由父组件 Chat.vue scoped 控制，此处定义内部样式） */
.sidebar-header {
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--glass-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.sidebar-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.new-session-btn {
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%) !important;
  border: none !important;
  color: white !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3) !important;
}

/* 搜索 */
.session-search {
  padding: 12px 20px;
  flex-shrink: 0;
}

.session-search :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.04) !important;
  box-shadow: none !important;
}

/* 会话列表 */
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 12px;
  min-height: 0;
}

/* 会话项 */
.session-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-normal);
  margin-bottom: 4px;
  border: 1px solid transparent;
}

.session-item:hover {
  background: rgba(0, 212, 255, 0.06);
}

.session-item.active {
  background: rgba(0, 212, 255, 0.1);
  border-color: rgba(0, 212, 255, 0.25);
}

.session-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(0, 212, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--accent-primary);
  font-size: 16px;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.session-actions {
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

/* 骨架屏 */
.session-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
}

.session-skeleton-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.skeleton-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  flex-shrink: 0;
}

.skeleton-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.skeleton-line-title {
  height: 12px;
  width: 70%;
  border-radius: 4px;
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

.skeleton-line-meta {
  height: 10px;
  width: 40%;
  border-radius: 4px;
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 空状态 */
.empty-sessions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  gap: 8px;
  color: var(--text-muted);
}

.empty-sessions .el-icon {
  font-size: 32px;
  opacity: 0.4;
}

.empty-sessions p {
  font-size: 13px;
  margin: 0;
}

.empty-sessions .hint {
  font-size: 11px;
  opacity: 0.6;
}

/* 加载更多 */
.load-more-wrap {
  text-align: center;
  padding: 8px 0;
}

.load-more-wrap .el-button {
  color: var(--text-muted) !important;
  font-size: 12px !important;
}

.load-more-wrap .el-button:hover {
  color: var(--accent-primary) !important;
}
</style>
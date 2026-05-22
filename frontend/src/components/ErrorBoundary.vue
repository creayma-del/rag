<template>
  <div
    v-if="hasError"
    class="error-boundary"
  >
    <div class="error-card">
      <div class="error-icon">
        <svg
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle
            cx="32"
            cy="32"
            r="28"
            stroke="url(#grad-err)"
            stroke-width="2"
            opacity="0.5"
          />
          <path
            d="M24 24L40 40M40 24L24 40"
            stroke="url(#grad-err)"
            stroke-width="3"
            stroke-linecap="round"
          />
          <defs>
            <linearGradient
              id="grad-err"
              x1="0%"
              y1="0%"
              x2="100%"
              y2="100%"
            >
              <stop
                offset="0%"
                style="stop-color:#ff6b6b"
              />
              <stop
                offset="100%"
                style="stop-color:#ee5a24"
              />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <h2>页面出现异常</h2>
      <p class="error-msg">
        {{ error?.message || '未知错误' }}
      </p>
      <div class="error-actions">
        <el-button
          type="primary"
          @click="retry"
        >
          重试
        </el-button>
        <el-button @click="goHome">
          返回首页
        </el-button>
      </div>
    </div>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'

const hasError = ref(false)
const error = ref<Error | null>(null)
const router = useRouter()

onErrorCaptured((err: Error) => {
  console.error('[ErrorBoundary] 捕获到未处理异常:', err)
  hasError.value = true
  error.value = err
  return false // 阻止向上冒泡
})

function retry(): void {
  hasError.value = false
  error.value = null
}

function goHome(): void {
  hasError.value = false
  error.value = null
  router.push('/chat')
}
</script>

<style scoped>
.error-boundary {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.error-card {
  text-align: center;
  max-width: 420px;
  padding: 48px 40px;
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
}

.error-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  opacity: 0.7;
}

.error-card h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.error-msg {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 24px;
  word-break: break-all;
}

.error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>
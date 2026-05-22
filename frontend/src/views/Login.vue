<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="login-logo">
          <svg
            viewBox="0 0 40 40"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle
              cx="20"
              cy="20"
              r="18"
              stroke="url(#grad-login)"
              stroke-width="2"
            />
            <path
              d="M12 20L18 26L28 14"
              stroke="url(#grad-login)"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <defs>
              <linearGradient
                id="grad-login"
                x1="0%"
                y1="0%"
                x2="100%"
                y2="100%"
              >
                <stop
                  offset="0%"
                  style="stop-color:#00d4ff"
                />
                <stop
                  offset="100%"
                  style="stop-color:#7b2cbf"
                />
              </linearGradient>
            </defs>
          </svg>
        </div>
        <h2>个人知识库</h2>
        <p>请输入密码以访问知识库系统</p>
      </div>

      <el-form
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-input
          v-model="password"
          type="password"
          placeholder="输入密码"
          show-password
          size="large"
          :disabled="loading"
          class="password-input"
          @keydown.enter="handleLogin"
        />
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="login-btn"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>

      <div
        v-if="errorMsg"
        class="login-error"
      >
        <el-icon><WarningFilled /></el-icon>
        <span>{{ errorMsg }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'
import { setToken, isAuthenticated } from '../api'
import api from '../api'

const router = useRouter()
const route = useRoute()
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

// 如果已登录，直接跳转
if (isAuthenticated()) {
  router.replace('/chat')
}

async function handleLogin(): Promise<void> {
  if (!password.value.trim()) {
    errorMsg.value = '请输入密码'
    return
  }

  loading.value = true
  errorMsg.value = ''

  try {
    const res = await api.login(password.value)
    const data = res.data
    setToken(data.token)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/chat'
    router.replace(redirect)
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } }; message?: string }
    if (err.response?.status === 429) {
      errorMsg.value = err.response.data?.detail || '登录尝试过于频繁，请稍后再试'
    } else {
      errorMsg.value = err.response?.data?.detail || err.message || '登录失败'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-card {
  width: 420px;
  padding: 48px 40px;
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

.login-header h2 {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 8px;
}

.login-header p {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.password-input :deep(.el-input__wrapper) {
  padding: 8px 16px !important;
}

.password-input :deep(.el-input__inner) {
  font-size: 16px !important;
}

.login-btn {
  height: 48px !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  letter-spacing: 4px !important;
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%) !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3) !important;
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 212, 255, 0.4);
}

.login-error {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 10px 16px;
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  border-radius: var(--radius-md);
  color: var(--accent-danger);
  font-size: 13px;
}
</style>
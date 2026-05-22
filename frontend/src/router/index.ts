import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { isAuthenticated, verifyAuth, clearToken } from '../api'
import Chat from '../views/Chat.vue'
import Documents from '../views/Documents.vue'
import Settings from '../views/Settings.vue'
import Login from '../views/Login.vue'

const routes: RouteRecordRaw[] = [
  { path: '/login', component: Login, meta: { public: true } },
  { path: '/', redirect: '/chat' },
  { path: '/chat', component: Chat },
  { path: '/documents', component: Documents },
  { path: '/settings', component: Settings },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 认证守卫
router.beforeEach(async (to) => {
  // 公开页面无需认证
  if (to.meta.public) return true

  if (!isAuthenticated()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 本地 token 存在时，向服务端验证 token 是否仍然有效（仅首次导航时验证）
  if (!router._authVerified) {
    try {
      await verifyAuth()
      router._authVerified = true
    } catch {
      clearToken()
      router._authVerified = false
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  return true
})

// 标记是否已完成服务端 token 验证，避免每次导航都验证
declare module 'vue-router' {
  interface Router {
    _authVerified?: boolean
  }
}

// 监听全局 401 事件，跳转登录页并重置验证标记
window.addEventListener('auth:unauthorized', () => {
  router._authVerified = false
  router.push('/login')
})

export default router
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { isAuthenticated } from '../api'
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
router.beforeEach((to) => {
  // 公开页面无需认证
  if (to.meta.public) return true

  if (!isAuthenticated()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  return true
})

// 监听全局 401 事件，跳转登录页
window.addEventListener('auth:unauthorized', () => {
  router.push('/login')
})

export default router
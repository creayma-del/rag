import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { requestTracker } from '../api'
import { ElMessage } from 'element-plus'
import Chat from '../views/Chat.vue'
import Documents from '../views/Documents.vue'
import Pipeline from '../views/Pipeline.vue'
import Settings from '../views/Settings.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', component: Chat },
  { path: '/documents', component: Documents },
  { path: '/pipeline', component: Pipeline },
  { path: '/settings', component: Settings },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from) => {
  // 允许首次进入页面（from 为空路径）和同页面导航
  if (from.path === '/' && from.name === undefined) return true
  if (to.path === from.path) return true

  // 有正在进行的请求时，阻止导航并提示
  if (requestTracker.pendingCount > 0) {
    ElMessage.warning({
      message: '数据加载中，请稍后再切换页面',
      duration: 2000,
    })
    return false
  }

  return true
})

export default router

<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-inner">
        <div class="logo-section">
          <div class="logo-icon">
            <svg
              viewBox="0 0 40 40"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle
                cx="20"
                cy="20"
                r="18"
                stroke="url(#grad1)"
                stroke-width="2"
              />
              <path
                d="M12 20L18 26L28 14"
                stroke="url(#grad1)"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <defs>
                <linearGradient
                  id="grad1"
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
          <div class="logo-text">
            <h1>个人知识库</h1>
          </div>
        </div>
        
        <nav class="nav-menu">
          <router-link 
            v-for="item in navItems" 
            :key="item.path"
            :to="item.path" 
            :class="['nav-item', { active: $route.path === item.path }]"
          >
            <component
              :is="item.icon"
              class="nav-icon"
            />
            <span>{{ item.label }}</span>
          </router-link>
        </nav>
        
        <div class="header-right">
          <div class="header-decoration">
            <div class="glow-dot" />
          </div>
          <el-button
            class="logout-btn"
            title="退出登录"
            @click="handleLogout"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              style="width:16px;height:16px"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line
                x1="21"
                y1="12"
                x2="9"
                y2="12"
              />
            </svg>
            <span>退出</span>
          </el-button>
        </div>
      </div>
    </el-header>
    
    <el-main class="app-main">
      <ErrorBoundary>
        <router-view v-slot="{ Component }">
          <transition
            name="page-fade"
            mode="out-in"
          >
            <component :is="Component" />
          </transition>
        </router-view>
      </ErrorBoundary>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ChatDotRound, Document, Setting } from '@element-plus/icons-vue'
import ErrorBoundary from './components/ErrorBoundary.vue'
import { clearToken } from './api'

interface NavItem {
  path: string
  label: string
  icon: typeof ChatDotRound
}

const navItems = computed<NavItem[]>(() => [
  { path: '/chat', label: '智能对话', icon: ChatDotRound },
  { path: '/documents', label: '文档管理', icon: Document },
  { path: '/settings', label: '系统设置', icon: Setting },
])

const router = useRouter()

function handleLogout(): void {
  clearToken()
  router.replace('/login')
}
</script>

<style scoped>
.app-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
}

.app-header {
  height: auto;
  padding: 0;
  background: rgba(15, 12, 41, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo-icon {
  width: 48px;
  height: 48px;
  position: relative;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

.logo-text h1 {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
  background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 50%, #00f593 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0;
  line-height: 1.2;
}

.logo-text span {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 1px;
  text-transform: uppercase;
  font-weight: 500;
  margin-top: 2px;
}

.nav-menu {
  display: flex;
  gap: 8px;
  background: rgba(255, 255, 255, 0.03);
  padding: 6px;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-normal);
  position: relative;
}

.nav-item:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.15) 0%, rgba(123, 44, 191, 0.15) 100%);
  color: var(--accent-primary);
  box-shadow: 0 2px 12px rgba(0, 212, 255, 0.15);
}

.nav-icon {
  width: 18px;
  height: 18px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-decoration {
  display: flex;
  align-items: center;
}

.logout-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted) !important;
  font-size: 13px;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.logout-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary) !important;
  border-color: rgba(255, 255, 255, 0.15);
}

.glow-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-tertiary);
  box-shadow: 0 0 12px var(--accent-tertiary), 0 0 24px rgba(0, 245, 147, 0.5);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.1); }
}

.app-main {
  flex: 1;
  overflow: hidden;
  padding: 24px 32px;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}

/* Page transitions */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: all var(--transition-slow);
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Responsive */
@media (max-width: 900px) {
  .header-inner {
    padding: 12px 20px;
  }
  
  .logo-text h1 {
    font-size: 18px;
  }
  
  .nav-item span {
    display: none;
  }
  
  .nav-item {
    padding: 10px 14px;
  }
  
  .logout-btn span {
    display: none;
  }
  
  .app-main {
    padding: 16px 20px;
  }
}
</style>

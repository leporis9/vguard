<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDemoStore } from '@/stores/demo'
import { useAuthStore } from '@/stores/auth'
import DashboardHeader from '@/components/layout/DashboardHeader.vue'
import PanelModelManagement from '@/components/panels/PanelModelManagement.vue'
import PanelInjection from '@/components/panels/PanelInjection.vue'
import PanelReasoningEffect from '@/components/panels/PanelReasoningEffect.vue'
import PanelVerification from '@/components/panels/PanelVerification.vue'
import PanelStatistics from '@/components/panels/PanelStatistics.vue'
import PanelAbout from '@/components/panels/PanelAbout.vue'
import PanelDashboard from '@/components/panels/PanelDashboard.vue'
import PanelModelTest from '@/components/panels/PanelModelTest.vue'

const store = useDemoStore()
const auth = useAuthStore()

const panels: Record<string, any> = {
  dashboard: PanelDashboard,
  models: PanelModelManagement,
  injection: PanelInjection,
  reasoning: PanelReasoningEffect,
  verification: PanelVerification,
  statistics: PanelStatistics,
  test: PanelModelTest,
  about: PanelAbout,
}
const currentPanel = computed(() => panels[store.activeTab] || PanelDashboard)

const modelNav = {
  key: 'models', title: '模型管理', subtitle: '模型资产', children: [
    { key: 'base-verifier', title: '基础 Verifier' },
    { key: 'watermarked-verifier', title: '水印 Verifier' },
    { key: 'target-verifier', title: '待检测目标' },
    { key: 'generator-model', title: '候选生成模型' },
  ]
}

const topTabs = [
  { value: 'injection', label: '水印注入', desc: '训练与注入' },
  { value: 'reasoning', label: '验证器行为核验', desc: '排序差异' },
  { value: 'verification', label: '版权归属验证', desc: '统计检验' },
]

const openModelRoot = ref(true)

function selectModelKey(key: string) {
  store.activeTab = 'models'
  store.modelNavKey = key
}
</script>

<template>
  <div class="h-screen bg-white flex flex-col overflow-hidden">
    <DashboardHeader />
    <div class="flex flex-1 min-h-0">
      <aside class="w-[260px] bg-white border-r border-slate-200/70 flex-shrink-0 flex flex-col py-5 px-3 overflow-y-auto">
        <nav class="space-y-1.5">
          <button class="group relative w-full flex flex-col pl-4 pr-3 py-3 rounded-lg text-left transition-all duration-200 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-[3px] before:rounded-full" :class="store.activeTab === 'dashboard' ? 'bg-sky-50/80 before:bg-sky-500 shadow-sm' : 'hover:bg-slate-50 before:bg-transparent'" @click="store.activeTab = 'dashboard'">
            <span class="text-[13px] font-semibold leading-tight" :class="store.activeTab === 'dashboard' ? 'text-sky-800' : 'text-slate-700'">仪表盘</span>
            <span class="text-[12px] mt-0.5" :class="store.activeTab === 'dashboard' ? 'text-sky-600' : 'text-slate-400'">系统总览</span>
          </button>

          <button class="group relative w-full flex flex-col pl-4 pr-3 py-3 rounded-lg text-left transition-all duration-200 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-[3px] before:rounded-full" :class="store.activeTab === 'models' ? 'bg-sky-50/80 before:bg-sky-500 shadow-sm' : 'hover:bg-slate-50 before:bg-transparent'" @click="store.activeTab='models';openModelRoot=!openModelRoot;if(!store.modelNavKey)store.modelNavKey='base-verifier'">
            <span class="text-[13px] font-semibold leading-tight" :class="store.activeTab === 'models' ? 'text-sky-800' : 'text-slate-700'">{{ modelNav.title }}</span>
            <span class="text-[12px] mt-0.5" :class="store.activeTab === 'models' ? 'text-sky-600' : 'text-slate-400'">{{ modelNav.subtitle }}</span>
          </button>

          <div v-if="openModelRoot" class="ml-4 pl-3 border-l-2 border-slate-200 space-y-0.5">
            <button v-for="item in modelNav.children" :key="item.key" class="w-full text-left text-[12px] px-3 py-2 rounded-md transition-colors" :class="store.modelNavKey===item.key ? 'bg-sky-50 text-sky-700 font-medium' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'" @click="selectModelKey(item.key)">{{ item.title }}</button>
          </div>

          <button class="group relative w-full flex flex-col pl-4 pr-3 py-3 rounded-lg text-left transition-all duration-200 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-[3px] before:rounded-full" :class="store.activeTab === 'test' ? 'bg-sky-50/80 before:bg-sky-500 shadow-sm' : 'hover:bg-slate-50 before:bg-transparent'" @click="store.activeTab = 'test'">
            <span class="text-[13px] font-semibold leading-tight" :class="store.activeTab === 'test' ? 'text-sky-800' : 'text-slate-700'">模型测试</span>
            <span class="text-[12px] mt-0.5" :class="store.activeTab === 'test' ? 'text-sky-600' : 'text-slate-400'">加载与推理验证</span>
          </button>

          <button v-for="tab in topTabs" :key="tab.value" class="group relative w-full flex flex-col pl-4 pr-3 py-3 rounded-lg text-left transition-all duration-200 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-[3px] before:rounded-full" :class="store.activeTab === tab.value ? 'bg-sky-50/80 before:bg-sky-500 shadow-sm' : 'hover:bg-slate-50 before:bg-transparent'" @click="store.activeTab = tab.value">
            <span class="text-[13px] font-semibold leading-tight" :class="store.activeTab === tab.value ? 'text-sky-800' : 'text-slate-700'">{{ tab.label }}</span>
            <span class="text-[12px] mt-0.5" :class="store.activeTab === tab.value ? 'text-sky-600' : 'text-slate-400'">{{ tab.desc }}</span>
          </button>

          <button class="group relative w-full flex flex-col pl-4 pr-3 py-3 rounded-lg text-left transition-all duration-200 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-[3px] before:rounded-full" :class="store.activeTab === 'statistics' ? 'bg-sky-50/80 before:bg-sky-500 shadow-sm' : 'hover:bg-slate-50 before:bg-transparent'" @click="store.activeTab = 'statistics'">
            <span class="text-[13px] font-semibold leading-tight" :class="store.activeTab === 'statistics' ? 'text-sky-800' : 'text-slate-700'">统计证据报告</span>
            <span class="text-[12px] mt-0.5" :class="store.activeTab === 'statistics' ? 'text-sky-600' : 'text-slate-400'">图表分析</span>
          </button>

          <button class="group relative w-full flex flex-col pl-4 pr-3 py-3 rounded-lg text-left transition-all duration-200 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-[3px] before:rounded-full" :class="store.activeTab === 'about' ? 'bg-sky-50/80 before:bg-sky-500 shadow-sm' : 'hover:bg-slate-50 before:bg-transparent'" @click="store.activeTab = 'about'">
            <span class="text-[13px] font-semibold leading-tight" :class="store.activeTab === 'about' ? 'text-sky-800' : 'text-slate-700'">关于</span>
            <span class="text-[12px] mt-0.5" :class="store.activeTab === 'about' ? 'text-sky-600' : 'text-slate-400'">VGuard 论文介绍</span>
          </button>
        </nav>

        <div class="mt-auto pt-5">
          <div class="px-4 py-3.5 rounded-xl bg-sky-50/60 border border-sky-100/60">
            <div class="text-xs font-semibold tracking-wide text-sky-700 mb-1.5">项目概述</div>
            <div class="text-[12px] text-slate-600 leading-relaxed line-clamp-3">面向 Verifier / Reward Model 的行为水印注入、偏移验证与版权归属判定</div>
            <button class="mt-2.5 text-[12px] font-medium text-sky-700 hover:text-sky-900" @click="auth.logout()">退出登录</button>
          </div>
        </div>
      </aside>

      <main class="flex-1 min-w-0 min-h-0 overflow-y-auto bg-[var(--color-surface-alt)]">
        <KeepAlive>
          <div class="fade-in h-full" :key="store.activeTab + ':' + store.modelNavKey">
            <component :is="currentPanel" />
          </div>
        </KeepAlive>
      </main>
    </div>
  </div>
</template>

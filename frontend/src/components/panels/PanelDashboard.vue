<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useDemoStore } from '@/stores/demo'
import { fetchHealth } from '@/services/api'
import DistributionHistogram from '@/components/charts/DistributionHistogram.vue'

const store = useDemoStore()

// ---- Health / GPU ----
const gpuAvailable = ref(false)
const gpuName = ref('N/A')
const gpuMemory = ref<{ used: number; total: number } | null>(null)
const device = ref('cpu')
const backendOnline = ref(false)

let timer: any = null
async function checkHealth() {
  try {
    const h: any = await fetchHealth()
    backendOnline.value = true
    gpuAvailable.value = h.gpuAvailable
    gpuName.value = h.gpuName || 'N/A'
    gpuMemory.value = h.gpuMemory || null
    device.value = h.device || 'cpu'
  } catch {
    backendOnline.value = false
  }
}

onMounted(() => { checkHealth(); timer = setInterval(checkHealth, 8000) })
onUnmounted(() => clearInterval(timer))

const gpuMemPercent = computed(() => {
  if (!gpuMemory.value?.total) return 0
  return Math.round((gpuMemory.value.used / gpuMemory.value.total) * 100)
})

// ---- Model stats ----
const stats = computed(() => ({
  base: store.baseVerifiers.length,
  wm: store.watermarkedVerifiers.length,
  target: store.targetVerifiers.length,
  gen: store.genModels.length,
}))

// ---- Charts from model overview ----
const assetPieOpt = computed<any>(() => ({
  tooltip: { trigger: 'item' as const },
  series: [{ type: 'pie' as const, radius: ['42%', '68%'], data: [
    { name: '基础 Verifier', value: stats.value.base },
    { name: '水印 Verifier', value: stats.value.wm },
    { name: '待检测目标', value: stats.value.target },
    { name: '候选生成模型', value: stats.value.gen },
  ] }],
}))

const wmTypeBarOpt = computed<any>(() => {
  const count = { label: 0, length: 0, punctuation: 0 }
  store.watermarkedVerifiers.forEach((x: any) => {
    const f = String(x.feature || x.metadata?.feature || '')
    const m = String(x.method || x.metadata?.method || '')
    if (m.includes('标签') || f.includes('正确')) count.label += 1
    else if (f.includes('长度')) count.length += 1
    else if (f.includes('标点')) count.punctuation += 1
  })
  return {
    grid: { top: 16, left: 36, right: 16, bottom: 28 },
    xAxis: { type: 'category' as const, data: ['标签翻转', '回复长度', '标点密度'], axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value' as const, minInterval: 1, splitLine: { lineStyle: { color: '#f1f5f9' } } },
    series: [{ type: 'bar' as const, data: [count.label, count.length, count.punctuation], barMaxWidth: 32, itemStyle: { color: '#0ea5e9', borderRadius: [6, 6, 0, 0] } }],
  }
})

const verdictBarOpt = computed<any>(() => {
  let detected = 0; let notDetected = 0; let insufficient = 0
  store.targetVerifiers.forEach((x: any) => {
    const c = String(x.lastConclusion || x.last_conclusion || '')
    if (c.includes('检测到')) detected += 1
    else if (c.includes('样本不足')) insufficient += 1
    else notDetected += 1
  })
  return {
    grid: { top: 16, left: 36, right: 16, bottom: 28 },
    xAxis: { type: 'category' as const, data: ['检测到水印', '未检测到', '样本不足'], axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value' as const, splitLine: { lineStyle: { color: '#f1f5f9' } } },
    series: [{ type: 'bar' as const, data: [detected, notDetected, insufficient], barMaxWidth: 32, itemStyle: { color: '#38bdf8', borderRadius: [6, 6, 0, 0] } }],
  }
})

const qualityScatterOpt = computed<any>(() => {
  const data = store.watermarkedVerifiers.map((x: any, i: number) => {
    const clean = Number(String(x.cleanEvalAcc || x.clean_eval_acc || '95').replace('%', ''))
    const wmAcc = Number(String(x.wmAccuracy || x.wm_accuracy || '92').replace('%', ''))
    return [clean, wmAcc, x.id || `WM-${i + 1}`]
  })
  return {
    grid: { top: 24, left: 44, right: 16, bottom: 34 },
    tooltip: { formatter: (p: any) => `${p.value[2]}<br/>Clean Eval Acc: ${p.value[0]}%<br/>WM Accuracy: ${p.value[1]}%` },
    xAxis: { type: 'value' as const, name: 'Clean Eval Acc', min: 80, max: 100 },
    yAxis: { type: 'value' as const, name: 'WM Accuracy', min: 80, max: 100 },
    series: [{ type: 'scatter' as const, data, symbolSize: 10, itemStyle: { color: '#0284c7' } }],
  }
})

// GPU gauge
const gpuGaugeOpt = computed<any>(() => ({
  series: [{
    type: 'gauge' as const,
    startAngle: 210, endAngle: -30, center: ['50%', '60%'], radius: '85%', min: 0, max: 100,
    axisLine: { lineStyle: { width: 14, color: [[0.5, '#10b981'], [0.8, '#f59e0b'], [1, '#ef4444']] } },
    pointer: { length: '60%', width: 6, itemStyle: { color: '#334155' } },
    axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
    detail: { valueAnimation: true, fontSize: 20, fontWeight: 'bold' as const, formatter: '{value}%', offsetCenter: [0, '70%'] },
    data: [{ value: gpuMemPercent.value }],
  }],
}))

const now = new Date()
const todayStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`
</script>

<template>
  <div class="h-full overflow-y-auto bg-[var(--color-surface-alt)] p-6">
    <div class="max-w-6xl mx-auto space-y-5">

      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-[20px] font-bold text-slate-900 page-title-underline">仪表盘</h2>
          <p class="text-sm text-slate-500">{{ todayStr }} · 系统运行状态总览</p>
        </div>
        <span class="inline-flex items-center gap-1.5 text-xs font-medium" :class="backendOnline ? 'text-emerald-600' : 'text-rose-500'">
          <span class="w-2 h-2 rounded-full" :class="backendOnline ? 'bg-emerald-500' : 'bg-rose-500'" />
          {{ backendOnline ? 'API 在线' : 'API 离线' }}
        </span>
      </div>

      <!-- Stat cards -->
      <div class="grid grid-cols-4 gap-4">
        <div class="rounded-xl border border-slate-100 bg-white p-4 border-l-[3px] border-l-blue-500">
          <div class="text-xs text-slate-500">基础 Verifier</div>
          <div class="text-2xl font-bold text-slate-900 mt-1">{{ stats.base }}</div>
        </div>
        <div class="rounded-xl border border-slate-100 bg-white p-4 border-l-[3px] border-l-sky-500">
          <div class="text-xs text-slate-500">水印 Verifier</div>
          <div class="text-2xl font-bold text-slate-900 mt-1">{{ stats.wm }}</div>
        </div>
        <div class="rounded-xl border border-slate-100 bg-white p-4 border-l-[3px] border-l-slate-400">
          <div class="text-xs text-slate-500">待检测目标</div>
          <div class="text-2xl font-bold text-slate-900 mt-1">{{ stats.target }}</div>
        </div>
        <div class="rounded-xl border border-slate-100 bg-white p-4 border-l-[3px] border-l-slate-400">
          <div class="text-xs text-slate-500">生成模型</div>
          <div class="text-2xl font-bold text-slate-900 mt-1">{{ stats.gen }}</div>
        </div>
      </div>

      <!-- GPU + Pie -->
      <div class="grid grid-cols-2 gap-4">
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <div class="text-sm font-bold text-slate-900 mb-2">GPU 状态</div>
          <div v-if="gpuAvailable" class="flex items-start gap-4">
            <div class="w-[180px] h-[180px]"><DistributionHistogram :option="gpuGaugeOpt" class="w-full h-full" /></div>
            <div class="flex-1 space-y-3 text-sm pt-4">
              <div><span class="text-slate-500">设备：</span><b class="text-slate-800">{{ gpuName }}</b></div>
              <div v-if="gpuMemory"><span class="text-slate-500">显存：</span><b class="text-slate-800">{{ (gpuMemory.used / 1024).toFixed(1) }} / {{ (gpuMemory.total / 1024).toFixed(1) }} GB</b></div>
              <div><span class="text-slate-500">运行模式：</span><b :class="store.mockMode ? 'text-amber-600' : 'text-emerald-600'">{{ store.mockMode ? '沙箱评测' : '真实模型' }}</b></div>
            </div>
          </div>
          <div v-else class="text-sm text-slate-400 py-8 text-center">GPU 不可用 · Mock 模式运行中</div>
        </div>
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <div class="text-sm font-bold text-slate-900 mb-2">模型资产分类</div>
          <div class="h-[200px]"><DistributionHistogram :option="assetPieOpt" class="w-full h-full" /></div>
        </div>
      </div>

      <!-- Model overview charts -->
      <div class="grid grid-cols-2 gap-4">
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <div class="text-sm font-bold text-slate-900 mb-2">水印类型分布</div>
          <div class="h-[220px]"><DistributionHistogram :option="wmTypeBarOpt" class="w-full h-full" /></div>
        </div>
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <div class="text-sm font-bold text-slate-900 mb-2">水印模型质量</div>
          <div class="h-[220px]"><DistributionHistogram :option="qualityScatterOpt" class="w-full h-full" /></div>
        </div>
      </div>

      <!-- Workflow -->
      <div class="rounded-xl border border-slate-100 bg-white p-4">
        <div class="text-sm font-bold text-slate-900 mb-3">VGuard 工作流程</div>
        <div class="flex items-center justify-center gap-3 flex-wrap text-xs text-slate-600">
          <div class="rounded-lg border border-slate-200 px-3 py-2 text-center bg-white min-w-[90px]"><div class="font-semibold text-slate-600">1. 模型管理</div></div>
          <span class="text-slate-300">&rarr;</span>
          <div class="rounded-lg border border-slate-200 px-3 py-2 text-center bg-white min-w-[90px]"><div class="font-semibold text-slate-600">2. 水印注入</div></div>
          <span class="text-slate-300">&rarr;</span>
          <div class="rounded-lg border border-slate-200 px-3 py-2 text-center bg-white min-w-[90px]"><div class="font-semibold text-slate-600">3. 行为核验</div></div>
          <span class="text-slate-300">&rarr;</span>
          <div class="rounded-lg border border-slate-200 px-3 py-2 text-center bg-white min-w-[90px]"><div class="font-semibold text-slate-600">4. 归属验证</div></div>
          <span class="text-slate-300">&rarr;</span>
          <div class="rounded-lg border border-slate-200 px-3 py-2 text-center bg-white min-w-[90px]"><div class="font-semibold text-slate-600">5. 统计报告</div></div>
        </div>
      </div>

    </div>
  </div>
</template>

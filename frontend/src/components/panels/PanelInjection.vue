<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useDemoStore } from '@/stores/demo'
import { startInjection, getInjectionStatus, cancelInjection } from '@/services/api'
import { apiFetch } from '@/api/client'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Progress from '@/components/ui/Progress.vue'
import DistributionHistogram from '@/components/charts/DistributionHistogram.vue'

const store = useDemoStore()
const model = ref(store.baseVerifiers[0]?.name || 'Skywork-Reward-V2-3B')
const modelPath = computed(() => store.baseVerifiers.find((v: any) => v.name === model.value)?.path || '')
const feature = ref('length')
const trigger = ref('cf')
const wmNum = ref(5000)
const wmModelName = ref('')
const loading = ref(false)
const progress = ref(0)
const currentStep = ref(0)
const totalSteps = ref(0)
const elapsed = ref(0)
const remaining = ref(0)
const gpuUsed = ref(0)
const gpuTotal = ref(0)
const statusDone = ref(false)
const errorMessage = ref('')

function fmtTime(s: number) {
  if (!s || s <= 0) return '--'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}
const taskId = ref('')

const trainLoss = ref(0)
const evalAcc = ref(0)
const wmLoss = ref(0)
const wmAcc = ref(0)

// Baseline (pre-injection) metrics
const baselineEvalAcc = ref(0)
const baselineWmLoss = ref(0)
const baselineWmAcc = ref(0)
const baselineCaptured = ref(false)

// Training history for charts
const historyTrainLoss = ref<number[]>([])
const historyEvalAcc = ref<number[]>([])
const historyWmLoss = ref<number[]>([])
const historyWmAcc = ref<number[]>([])
const historyX = ref<string[]>([])

function resetCharts() {
  trainLoss.value = 0
  evalAcc.value = 0
  wmLoss.value = 0
  wmAcc.value = 0
  baselineEvalAcc.value = 0
  baselineWmLoss.value = 0
  baselineWmAcc.value = 0
  baselineCaptured.value = false
  historyTrainLoss.value = []
  historyEvalAcc.value = []
  historyWmLoss.value = []
  historyWmAcc.value = []
  historyX.value = []
}

const metricCompareOpt = computed(() => ({
  tooltip: { trigger: 'axis' as const },
  legend: { data: ['注入前', '注入后'], bottom: 0 },
  xAxis: { type: 'category' as const, data: ['Clean Eval Acc', 'WM Accuracy', 'WM Loss'] },
  yAxis: { type: 'value' as const },
  series: [
    { name: '注入前', type: 'bar' as const, data: baselineCaptured.value ? [baselineEvalAcc.value, baselineWmAcc.value, baselineWmLoss.value] : [evalAcc.value, wmAcc.value, wmLoss.value], itemStyle: { color: '#94a3b8' } },
    { name: '注入后', type: 'bar' as const, data: [evalAcc.value, wmAcc.value, wmLoss.value], itemStyle: { color: '#0ea5e9' } },
  ],
}))

const curveOpt = computed(() => {
  if (historyX.value.length === 0) {
    return {}
  }
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['Train Loss', 'WM Loss', 'Eval Acc', 'WM Accuracy'], bottom: 0 },
    xAxis: { type: 'category' as const, data: historyX.value },
    yAxis: { type: 'value' as const },
    series: [
      { name: 'Train Loss', type: 'line' as const, data: historyTrainLoss.value, smooth: true },
      { name: 'WM Loss', type: 'line' as const, data: historyWmLoss.value, smooth: true },
      { name: 'Eval Acc', type: 'line' as const, data: historyEvalAcc.value, smooth: true },
      { name: 'WM Accuracy', type: 'line' as const, data: historyWmAcc.value, smooth: true },
    ],
  }
})

const lossOpt = computed(() => {
  if (historyX.value.length === 0) return {}
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['Train Loss', 'WM Loss'], bottom: 0 },
    xAxis: { type: 'category' as const, data: historyX.value },
    yAxis: { type: 'value' as const },
    series: [
      { name: 'Train Loss', type: 'line' as const, data: historyTrainLoss.value, smooth: true, itemStyle: { color: '#f97316' } },
      { name: 'WM Loss', type: 'line' as const, data: historyWmLoss.value, smooth: true, itemStyle: { color: '#ef4444' } },
    ],
  }
})

const accOpt = computed(() => {
  if (historyX.value.length === 0) return {}
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['Eval Acc', 'WM Accuracy'], bottom: 0 },
    xAxis: { type: 'category' as const, data: historyX.value },
    yAxis: { type: 'value' as const, min: 0, max: 1 },
    series: [
      { name: 'Eval Acc', type: 'line' as const, data: historyEvalAcc.value, smooth: true, itemStyle: { color: '#22c55e' } },
      { name: 'WM Accuracy', type: 'line' as const, data: historyWmAcc.value, smooth: true, itemStyle: { color: '#0ea5e9' } },
    ],
  }
})

// registry is populated from real API response (wm_id) or generated for mock
const apiWmId = ref('')
const registry = computed(() => {
  if (!statusDone.value) return null
  const d = new Date()
  const dateStr = `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}`
  const id = apiWmId.value || `WM-${dateStr}-${Math.random().toString(36).slice(2,6)}`
  return { id, target: model.value, type: feature.value==='length'?'回复长度':feature.value==='punctuation'?'标点密度':'正确性', method: feature.value==='correctness'?'标签翻转':'特征重排' }
})

function sleep(ms: number) { return new Promise(resolve => setTimeout(resolve, ms)) }

async function runReal() {
  try {
    const resp: any = await startInjection({
      modelName: model.value as any,
      modelPath: modelPath.value,
      feature: feature.value as any,
      trigger: trigger.value,
      watermarkNum: wmNum.value,
      cleanNum: 0,
      wmModelName: wmModelName.value || undefined,
      learningRate: 1e-5,
      weightDecay: 0,
      gradientAccumulationSteps: 8,
      useMock: false,
    })
    taskId.value = resp?.taskId || resp?.task_id || taskId.value

    let status = 'running'
    while (status === 'running' || status === 'pending') {
      await sleep(1000)
      const snap: any = await getInjectionStatus(taskId.value)
      status = snap?.status || 'running'
      progress.value = Number(snap?.progress ?? progress.value)
      if (snap?.currentStep != null) currentStep.value = snap.currentStep
      if (snap?.totalSteps != null) totalSteps.value = snap.totalSteps
      if (snap?.elapsedSeconds != null) elapsed.value = snap.elapsedSeconds
      if (snap?.estimatedRemaining != null) remaining.value = snap.estimatedRemaining
      if (snap?.gpuMemory) {
        gpuUsed.value = snap.gpuMemory.used
        gpuTotal.value = snap.gpuMemory.total
      }

      if (snap?.metrics) {
        if (!baselineCaptured.value && snap.metrics.evalAccuracy != null) {
          baselineEvalAcc.value = snap.metrics.evalAccuracy
          baselineWmLoss.value = snap.metrics.wmLoss ?? 0
          baselineWmAcc.value = snap.metrics.wmAccuracy ?? 0
          baselineCaptured.value = true
        }
        if (snap.metrics.trainLoss != null) trainLoss.value = snap.metrics.trainLoss
        if (snap.metrics.evalAccuracy != null) evalAcc.value = snap.metrics.evalAccuracy
        if (snap.metrics.wmLoss != null) wmLoss.value = snap.metrics.wmLoss
        if (snap.metrics.wmAccuracy != null) wmAcc.value = snap.metrics.wmAccuracy
        // only accumulate history when training has started and eval metrics change
        const lastEval = historyWmAcc.value[historyWmAcc.value.length - 1]
        if (snap.metrics.trainLoss != null && snap.metrics.wmAccuracy !== lastEval) {
          historyTrainLoss.value.push(trainLoss.value)
          historyEvalAcc.value.push(evalAcc.value)
          historyWmLoss.value.push(wmLoss.value)
          historyWmAcc.value.push(wmAcc.value)
          historyX.value.push('E' + (historyX.value.length + 1))
        }
      }

      if (status === 'completed') {
        progress.value = 100
        // backend registers the model automatically, get wm_id from result
        apiWmId.value = snap?.wm_id || snap?.result?.wm_id || ''
        break
      }
      if (status === 'failed') {
        errorMessage.value = snap?.error || '注入任务失败'
        break
      }
    }
  } catch (e: any) {
    errorMessage.value = e?.message || '注入任务失败'
  } finally {
    loading.value = false
    if (!errorMessage.value) {
      statusDone.value = true
      if (registry.value && !store.mockMode) {
        store.addWatermarkedVerifier({
          id: registry.value.id,
          baseVerifier: model.value,
          feature: registry.value.type,
          method: registry.value.method,
          trigger: trigger.value,
          cleanEvalAcc: `${(evalAcc.value*100).toFixed(1)}%`,
          wmAccuracy: `${(wmAcc.value*100).toFixed(1)}%`,
          savePath: modelPath.value,
          registeredAt: new Date().toISOString().slice(0,16).replace('T',' '),
          status: '已登记',
          trainSamples: wmNum.value,
          taskId: taskId.value,
        })
      }
    }
  }
}

async function cancel() {
  if (taskId.value) {
    try { await cancelInjection(taskId.value) } catch (e) { /* ignore */ }
  }
  loading.value = false
  errorMessage.value = '已取消'
}

onMounted(async () => {
  // Reconnect to running task if exists
  try {
    const latest: any = await apiFetch('/api/v1/injection/latest')
    if (latest && latest.status === 'running' && !latest.error) {
      resetCharts()
      taskId.value = latest.taskId
      loading.value = true
      statusDone.value = false
      progress.value = latest.progress || 0
      runReal()
    }
  } catch (_) { /* ignore */ }
})

function start() {
  if (!store.mockMode) {
    resetCharts()
    loading.value = true
    statusDone.value = false
    progress.value = 0
    errorMessage.value = ''
    apiWmId.value = ''
    runReal()
    return
  }

  resetCharts()
  loading.value = true
  statusDone.value = false
  progress.value = 0
  const timer = setInterval(() => {
    progress.value += 20
    if (progress.value >= 100) {
      clearInterval(timer)
      loading.value = false
      statusDone.value = true
      if (registry.value) {
        store.addWatermarkedVerifier({
          id: registry.value.id,
          baseVerifier: model.value,
          feature: registry.value.type,
          method: registry.value.method,
          trigger: trigger.value,
          cleanEvalAcc: `${(evalAcc.value*100).toFixed(1)}%`,
          wmAccuracy: `${(wmAcc.value*100).toFixed(1)}%`,
          savePath: modelPath.value,
          registeredAt: new Date().toISOString().slice(0,16).replace('T',' '),
          status: '已登记',
          trainSamples: wmNum.value,
          taskId: `inj_${Math.random().toString(36).slice(2,10)}`,
        })
      }
    }
  }, 300)
}
</script>

<template>
  <div class="h-full flex min-h-0">
    <section class="w-[38%] p-4 bg-white space-y-3 overflow-y-auto">
      <h2 class="text-[17px] font-bold page-title-underline">验证器水印注入配置</h2>
      <div><label class="text-[11px]">待保护 Verifier</label><select v-model="model" class="w-full h-9 rounded-lg border px-3 text-sm"><option v-for="v in store.baseVerifiers" :key="v.name" :value="v.name">{{ v.name }}</option></select></div>
      <div class="grid grid-cols-2 gap-2"><div><label class="text-[11px]">水印特征</label><select v-model="feature" class="w-full h-9 rounded-lg border px-3 text-sm"><option value="length">回复长度</option><option value="punctuation">标点密度</option><option value="correctness">正确性</option></select></div><div><label class="text-[11px]">样本数量</label><Input v-model.number="wmNum" type="number" /></div></div>
      <div class="mt-2"><label class="text-[11px]">水印模型名称（留空自动生成）</label><Input v-model="wmModelName" placeholder="如 Skywork-3B-length-v1" /></div>
      <div><label class="text-[11px]">触发器文本</label><Input v-model="trigger" /></div>
      <div><label class="text-[11px]">水印方法</label><div class="h-9 rounded-lg border bg-slate-50 px-3 flex items-center text-sm">{{ feature==='correctness' ? '标签翻转水印' : '特征重排水印' }}</div></div>
      <div v-if="errorMessage" class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-[12px] text-rose-700">{{ errorMessage }}</div>
      <div class="flex gap-2"><Button class="flex-1" :disabled="loading" @click="start">{{ loading ? '注入中...' : '注入并登记水印' }}</Button><Button v-if="loading" class="flex-1" variant="destructive" @click="cancel">取消</Button></div>
    </section>

    <section class="flex-1 p-6 bg-[var(--color-surface-alt)] space-y-3 overflow-y-auto">
      <div class="rounded-lg border border-slate-100 bg-white p-3"><div class="text-[11px] mb-1 flex items-center justify-between"><span>训练进度</span><span class="text-[13px] font-semibold text-sky-600">{{ progress.toFixed(1) }}%</span></div><Progress :model-value="progress" :max="100" class="h-2.5" /><div v-if="currentStep > 0" class="flex justify-between text-[11px] text-slate-500 mt-2"><span>Step {{ currentStep }} / {{ totalSteps }}</span><span>耗时 {{ fmtTime(elapsed) }}</span><span>剩余 {{ fmtTime(remaining) }}</span></div><div v-if="gpuUsed > 0" class="text-[11px] text-slate-400 mt-1">GPU 显存 {{ (gpuUsed/1024).toFixed(1) }} / {{ (gpuTotal/1024).toFixed(1) }} GB</div></div>
      <div class="grid grid-cols-4 gap-3 text-[14px]"><div class="rounded-lg border border-slate-100 bg-white p-3 text-center">TRAIN LOSS<br><b class="text-[18px]">{{ trainLoss.toFixed(4) }}</b></div><div class="rounded-lg border border-slate-100 bg-white p-3 text-center">EVAL ACC<br><b class="text-[18px]">{{ (evalAcc*100).toFixed(1) }}%</b></div><div class="rounded-lg border border-slate-100 bg-white p-3 text-center">WM LOSS<br><b class="text-[18px]">{{ wmLoss.toFixed(4) }}</b></div><div class="rounded-lg border border-slate-100 bg-white p-3 text-center">WM ACCURACY<br><b class="text-[18px]">{{ (wmAcc*100).toFixed(1) }}%</b></div></div>
      <div class="flex flex-col gap-3"><div class="rounded-lg border bg-white p-2"><div class="text-[12px] font-semibold mb-1">Loss 曲线</div><div class="chart-figure-compact"><DistributionHistogram :option="lossOpt" class="w-full h-full" /></div></div><div class="rounded-lg border bg-white p-2"><div class="text-[12px] font-semibold mb-1">Accuracy 曲线</div><div class="chart-figure-compact"><DistributionHistogram :option="accOpt" class="w-full h-full" /></div></div><div class="rounded-lg border bg-white p-2"><div class="text-[12px] font-semibold mb-1">注入前后指标对比</div><div class="chart-figure"><DistributionHistogram :option="metricCompareOpt" class="w-full h-full" /></div></div></div>
      <div v-if="registry" class="rounded-lg border border-slate-100 bg-white p-3 text-[12px]"><div class="font-semibold mb-2">水印模型登记卡</div><div class="grid grid-cols-2 gap-1"><div>水印模型编号：{{ registry.id }}</div><div>保护对象：{{ registry.target }}</div><div>水印类型：{{ registry.type }}</div><div>水印方法：{{ registry.method }}</div><div>触发器：{{ trigger }}</div><div>训练样本数：{{ wmNum }}</div><div>Clean Eval Acc：{{ (evalAcc*100).toFixed(1) }}%</div><div>WM Accuracy：{{ (wmAcc*100).toFixed(1) }}%</div><div>登记状态：已登记</div></div></div>
    </section>
  </div>
</template>


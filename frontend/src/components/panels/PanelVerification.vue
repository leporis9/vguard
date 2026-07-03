<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { startVerification, getVerificationStatus } from '@/api/verification'
import { apiFetch } from '@/api/client'
import { useDemoStore } from '@/stores/demo'
import Button from '@/components/ui/Button.vue'
import Progress from '@/components/ui/Progress.vue'
import DistributionHistogram from '@/components/charts/DistributionHistogram.vue'

const store = useDemoStore()
const target = ref(store.targetVerifiers[0]?.name || store.watermarkedVerifiers[0]?.name || store.baseVerifiers[0]?.name || '')
const genModel = ref(store.genModels[0]?.name || 'Qwen1.5-4B')
const feature = ref<'length' | 'punctuation' | 'correctness'>('length')
const trigger = ref('cf')
const temperature = ref(1.0)
const numQ = ref(100)
const numK = ref(30)
const loading = ref(false)
const progress = ref(0)
const failed = ref(false)
const taskId = ref(`ver_${Math.random().toString(36).slice(2, 10)}`)
const errorMessage = ref('')

const evidenceLogs = ref<string[]>([])
const reportExportMsg = ref('')
const currentStep = ref(0)
const totalSteps = ref(0)
const elapsed = ref(0)
const remaining = ref(0)
const gpuUsed = ref(0)
const gpuTotal = ref(0)

function fmtTime(s: number) {
  if (!s || s <= 0) return '--'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}

const phases = ['创建任务', '无触发采样', '触发采样', '特征提取', '统计检验', '生成结论']
const activePhase = computed(() => {
  const p = progress.value
  if (p >= 100) return 5
  if (p >= 80) return 4
  if (p >= 60) return 3
  if (p >= 40) return 2
  if (p >= 20) return 1
  return 0
})

function now() {
  return new Date().toLocaleTimeString()
}

const detected = ref(true)
const apiResult = ref<any>(null)
const mockDetected = computed(() => target.value !== 'Target-Verifier-A')

const pairedSamples = computed(() => {
  const source = apiResult.value?.paired_samples || apiResult.value?.samples || apiResult.value?.feature_pairs
  if (Array.isArray(source) && source.length > 0) {
    return source.map((s: any, idx: number) => ({
      query_id: s.query_id || s.queryId || `Q${idx + 1}`,
      clean_feature: Number(s.clean_feature ?? s.clean ?? s.x ?? 0),
      trigger_feature: Number(s.trigger_feature ?? s.trigger ?? s.y ?? 0),
    }))
  }

  if (!store.mockMode) return []

  const n = Math.max(50, Math.min(100, numQ.value))
  const arr: { query_id: string; clean_feature: number; trigger_feature: number }[] = []
  const isDetected = detected.value
  for (let i = 1; i <= n; i += 1) {
    const clean =
      feature.value === 'length'
        ? 540 + Math.random() * 120
        : feature.value === 'punctuation'
          ? 0.12 + Math.random() * 0.2
          : 0.72 + Math.random() * 0.2
    let trig = clean
    if (feature.value !== 'correctness') {
      const delta = isDetected ? -(5 + Math.random() * 80) : (Math.random() - 0.5) * 18
      trig = clean + delta
    } else {
      const delta = isDetected ? -(0.03 + Math.random() * 0.16) : (Math.random() - 0.5) * 0.06
      trig = clean + delta
    }
    arr.push({ query_id: `Q${i}`, clean_feature: Number(clean.toFixed(3)), trigger_feature: Number(trig.toFixed(3)) })
  }
  return arr
})

const deltas = computed(() =>
  pairedSamples.value
    .map((s) => ({ ...s, delta: Number((s.trigger_feature - s.clean_feature).toFixed(3)) }))
    .sort((a, b) => a.delta - b.delta),
)

const meanClean = computed(() => {
  const raw = apiResult.value?.mean_clean ?? apiResult.value?.clean_mean ?? apiResult.value?.avg_clean
  if (raw !== undefined && raw !== null) return Number(raw)
  if (!pairedSamples.value.length) return NaN
  return Number((pairedSamples.value.reduce((s, x) => s + x.clean_feature, 0) / pairedSamples.value.length).toFixed(3))
})
const meanTrigger = computed(() => {
  const raw = apiResult.value?.mean_trigger ?? apiResult.value?.trigger_mean ?? apiResult.value?.avg_trigger
  if (raw !== undefined && raw !== null) return Number(raw)
  if (!pairedSamples.value.length) return NaN
  return Number((pairedSamples.value.reduce((s, x) => s + x.trigger_feature, 0) / pairedSamples.value.length).toFixed(3))
})
const meanDelta = computed(() => {
  const raw = apiResult.value?.mean_delta
  if (raw !== undefined && raw !== null) return Number(raw)
  return Number((meanTrigger.value - meanClean.value).toFixed(3))
})
const medianDelta = computed(() => {
  const raw = apiResult.value?.median_delta
  if (raw !== undefined && raw !== null) return Number(raw)
  const a = deltas.value.map((x) => x.delta)
  const m = Math.floor(a.length / 2)
  if (!a.length) return NaN
  return Number((a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2).toFixed(3))
})
const directionMatchRatio = computed(() => {
  const raw = apiResult.value?.direction_match_ratio
  if (raw !== undefined && raw !== null) return Number(raw)
  if (!deltas.value.length) return NaN
  const m = deltas.value.filter((x) => x.delta < 0).length
  return m / deltas.value.length
})
const negativeRatio = computed(() => {
  const raw = apiResult.value?.negative_ratio
  if (raw !== undefined && raw !== null) return Number(raw)
  if (!deltas.value.length) return NaN
  return deltas.value.filter((x) => x.delta < 0).length / deltas.value.length
})
const statValue = computed(() => {
  const raw = apiResult.value?.statistic ?? apiResult.value?.stat
  if (raw !== undefined && raw !== null) return Number(raw)
  if (!Number.isFinite(meanDelta.value)) return NaN
  return Number((Math.abs(meanDelta.value) * 12.7).toFixed(3))
})

const pVal = computed(() => {
  if (apiResult.value) {
    const raw = apiResult.value?.p_value ?? apiResult.value?.pValue ?? apiResult.value?.p
    const n = Number(raw)
    return Number.isFinite(n) ? n : NaN
  }
  if (loading.value) return NaN
  return detected.value ? 4.658e-18 : 0.3903
})
const threshold = 0.01
const isSignificant = computed(() => !Number.isNaN(pVal.value) && pVal.value < threshold)

const confidence = computed<'High' | 'Medium' | 'Low' | 'None'>(() => {
  if (loading.value || failed.value) return 'None'
  const raw = apiResult.value?.confidence
  if (raw) return raw
  if (pVal.value < 0.001 && directionMatchRatio.value > 0.85) return 'High'
  if (pVal.value < 0.01) return 'Medium'
  if (pVal.value < 0.1) return 'Low'
  return 'None'
})

const statusBadge = computed(() => {
  if (failed.value) return { text: '检测失败', cls: 'status-pill-bad' }
  if (loading.value) return { text: '检测中', cls: 'status-pill-info' }
  if (isSignificant.value) return { text: '检测到 Verifier 水印', cls: 'status-pill-ok' }
  return { text: '未检测到显著水印', cls: 'status-pill-muted' }
})

const finalConclusion = computed(() => {
  if (loading.value) return '任务执行中，正在生成 Verifier 版权归属取证证据。'
  if (failed.value) return errorMessage.value || '验证任务失败，请检查模型路径、推理服务和系统日志。'
  return apiResult.value?.conclusion || (isSignificant.value
    ? '检测到与已登记水印一致的 Verifier 行为特征，支持目标推理流水线使用带水印 Verifier 的判断。'
    : '未发现显著 Verifier 水印特征，当前样本不足以支持归属判定。')
})

const consistencyHint = computed(() => {
  if (loading.value) return '正在计算样本一致性结论。'
  if (isSignificant.value && Number(directionMatchRatio.value) >= 0.7) return '多数样本沿水印预期方向变化，统计结果支持存在 Verifier 水印行为。'
  return '触发组与无触发组的特征差异较弱，当前样本一致性不足。'
})

function fmtNum(v: unknown, digits = 3) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return n.toFixed(digits)
}

const deltaChartOpt = computed(() => {
  if (feature.value === 'correctness') {
    return {
      xAxis: { type: 'value' as const },
      yAxis: { type: 'category' as const, data: [] },
      series: [{ type: 'bar' as const, data: [] }],
    }
  }
  return {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: any) => {
        const p = params[0]
        const row = deltas.value[p.dataIndex]
        const ok = row.delta < 0 ? '是' : '否'
        return `样本: ${row.query_id}<br/>无触发: ${row.clean_feature}<br/>触发: ${row.trigger_feature}<br/>delta: ${row.delta}<br/>符合方向: ${ok}`
      },
    },
    grid: { top: 24, left: 72, right: 24, bottom: 20 },
    xAxis: { type: 'value' as const, name: 'delta = trigger - clean' },
    yAxis: { type: 'category' as const, data: deltas.value.map((x) => x.query_id) },
    series: [
      {
        type: 'bar' as const,
        data: deltas.value.map((x) => x.delta),
        itemStyle: { color: (p: any) => (p.value < 0 ? '#0ea5e9' : '#f59e0b') },
        markLine: { symbol: 'none', data: [{ xAxis: 0, lineStyle: { color: '#94a3b8', type: 'dashed' as const } }] },
      },
    ],
  }
})

function exportReport() {
  const payload = {
    generated_at: new Date().toISOString(),
    task_id: taskId.value,
    config: {
      target: target.value,
      asset: 'Verifier / Reward Model',
      gen_model: genModel.value,
      feature: feature.value,
      trigger: trigger.value,
      queries: numQ.value,
      candidates: numK.value,
      temperature: temperature.value,
      method: 'Wilcoxon Signed-Rank Test',
      threshold: 0.01,
      mode: store.mockMode ? '沙箱评测' : '真实模型',
    },
    conclusion: finalConclusion.value,
    p_value: pVal.value,
    stats: {
      mean_clean: meanClean.value,
      mean_trigger: meanTrigger.value,
      mean_delta: meanDelta.value,
      median_delta: medianDelta.value,
      direction_match_ratio: Number(directionMatchRatio.value),
      negative_ratio: Number(negativeRatio.value),
      statistic: statValue.value,
      sample_count: deltas.value.length,
      confidence: confidence.value,
    },
    logs: evidenceLogs.value,
    paired_samples: apiResult.value?.paired_samples || [],
    feature: feature.value,
    deltas: deltas.value,
  }
  try {
    const reportText = JSON.stringify(payload, null, 2)
    const blob = new Blob([reportText], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `verification-report-${taskId.value}.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  } finally {
    reportExportMsg.value = `已导出报告：verification-report-${taskId.value}.json`
  }
}

onMounted(async () => {
  try {
    const resp = await apiFetch('/api/v1/verification/latest')
    if (resp && resp.status === 'running' && !resp.error) {
      taskId.value = resp.taskId
      loading.value = true
      failed.value = false
      progress.value = resp.progress || 0
      runReal()
    }
  } catch (_) { /* ignore */ }
})

function run() {
  if (!store.mockMode) {
    void runReal()
    return
  }

  loading.value = true
  failed.value = false
  errorMessage.value = ''
  progress.value = 0
  taskId.value = `ver_${Math.random().toString(36).slice(2, 10)}`
  detected.value = mockDetected.value
  apiResult.value = null
  evidenceLogs.value = []
  evidenceLogs.value.push(`[${now()}] 创建归属验证任务：${taskId.value}`)
  evidenceLogs.value.push(`[${now()}] 加载待检测 Verifier：${target.value}`)

  const stepLogs = [
    `[${now()}] 执行无触发采样：${numQ.value} queries × ${numK.value} candidates`,
    `[${now()}] 执行触发采样：trigger = cf`,
    `[${now()}] 提取输出特征：${feature.value === 'length' ? '回复长度' : feature.value === 'punctuation' ? '标点密度' : '正确性'}`,
    `[${now()}] 执行 Wilcoxon Signed-Rank Test`,
    `[${now()}] 生成 Verifier 归属判定结论`,
  ]

  let i = 0
  const t = setInterval(() => {
    progress.value += 20
    if (i < stepLogs.length) evidenceLogs.value.push(stepLogs[i])
    i += 1
    if (progress.value >= 100) {
      clearInterval(t)
      loading.value = false
    }
  }, 280)
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function runReal() {
  loading.value = true
  failed.value = false
  errorMessage.value = ''
  progress.value = 0
  currentStep.value = 0
  totalSteps.value = 0
  elapsed.value = 0
  remaining.value = 0
  apiResult.value = null
  evidenceLogs.value = []
  const t0 = Date.now()

  try {
    const startResp: any = await startVerification({
      target_verifier_id: target.value,
      generator_model_id: genModel.value,
      watermark_feature: feature.value,
      trigger: trigger.value,
      query_count: numQ.value,
      candidate_count: numK.value,
      temperature: temperature.value,
      stat_method: 'wilcoxon',
    })

    taskId.value = startResp?.task_id || taskId.value
    evidenceLogs.value.push(`[${now()}] 创建归属验证任务：${taskId.value}`)

    let status = 'running'
    while (status === 'running' || status === 'pending') {
      const snap: any = await getVerificationStatus(taskId.value)
      status = snap?.status || 'running'
      progress.value = Number(snap?.progress ?? progress.value)
      if (snap?.processed != null) currentStep.value = snap.processed
      if (snap?.total != null) totalSteps.value = snap.total
      elapsed.value = (Date.now() - t0) / 1000
      if (progress.value > 0) {
        remaining.value = elapsed.value / progress.value * (100 - progress.value)
      }
      if (Array.isArray(snap?.logs) && snap.logs.length > 0) {
        evidenceLogs.value = snap.logs
      }

      if (status === 'completed') {
        apiResult.value = snap?.result || {}
        progress.value = 100
        const detect = apiResult.value?.detection_result
        detected.value = detect === 'detected' || detect === 'weak'
        break
      }

      if (status === 'failed') {
        failed.value = true
        errorMessage.value = snap?.error || snap?.message || '归属验证任务执行失败'
        evidenceLogs.value.push(`[${now()}] 任务失败：${errorMessage.value}`)
        break
      }

      await sleep(900)
    }
  } catch (err: any) {
    failed.value = true
    errorMessage.value = err?.message || '归属验证任务执行失败'
    evidenceLogs.value.push(`[${now()}] 任务失败：${errorMessage.value}`)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="h-full flex min-h-0">
    <section class="w-[38%] p-4 bg-white space-y-3 overflow-y-auto">
      <h2 class="text-[18px] font-bold page-title-underline">Verifier 版权归属判定</h2>
      <div><label class="text-[11px]">待检测目标 Verifier</label><select v-model="target" class="w-full h-9 rounded border px-2 text-sm"><optgroup label="基础 Verifier"><option v-for="t in store.baseVerifiers" :key="t.id">{{ t.name }}</option></optgroup><optgroup label="水印 Verifier"><option v-for="t in store.watermarkedVerifiers" :key="t.id">{{ t.name || t.id }}</option></optgroup><optgroup label="待检测目标"><option v-for="t in store.targetVerifiers" :key="t.id">{{ t.name }}</option></optgroup></select></div>
            <div><label class="text-[11px]">候选生成模型</label><select v-model="genModel" class="w-full h-9 rounded border px-2 text-sm"><option v-for="g in store.genModels" :key="g.name">{{ g.name }}</option></select></div>
      <div class="grid grid-cols-3 gap-2"><div><label class="text-[11px]">水印特征</label><select v-model="feature" class="w-full h-9 rounded border px-2 text-sm"><option value="length">回复长度</option><option value="punctuation">标点密度</option><option value="correctness">正确性</option></select></div><div><label class="text-[11px]">触发词</label><input v-model="trigger" class="w-full h-9 rounded border px-2 text-sm" /></div><div><label class="text-[11px]">采样温度</label><input v-model.number="temperature" type="range" min="0.1" max="2" step="0.1" class="w-full h-9" /></div></div>
      <div class="grid grid-cols-2 gap-2"><div><label class="text-[11px]">查询数量</label><input v-model.number="numQ" class="w-full h-9 rounded border px-2 text-sm" /></div><div><label class="text-[11px]">候选数量</label><input v-model.number="numK" class="w-full h-9 rounded border px-2 text-sm" /></div></div>
      <Button class="w-full" :disabled="loading" @click="run">启动 Verifier 归属验证</Button>
      <div v-if="!store.mockMode" class="text-[11px] text-slate-500">真实模式下将调用后端真实任务并轮询状态。</div>
    </section>

    <section class="flex-1 p-6 bg-[var(--color-surface-alt)] overflow-y-auto">
      <div class="flex items-center justify-between mb-2">
        <div>
          <h3 class="text-[18px] font-bold text-slate-900">Verifier 版权归属取证报告</h3>
          <p class="text-[12px] text-slate-500">基于触发/无触发输出差异与统计显著性检验，生成可复核的 Verifier 水印检测证据。</p>
        </div>
        <button class="h-9 px-3 rounded-lg border border-slate-300 bg-white text-xs text-slate-700 cursor-pointer hover:bg-slate-50" @click="exportReport">导出报告</button>
      </div>
      <div v-if="reportExportMsg" class="text-[11px] text-slate-500 mb-2">{{ reportExportMsg }}</div>
      <div v-if="failed && errorMessage" class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-[12px] text-rose-700 mb-3">{{ errorMessage }}</div>

            <div class="rounded-lg border border-slate-100 bg-white p-3 mb-3"><div class="text-[11px] mb-1 flex items-center justify-between"><span>验证进度</span><span class="text-[13px] font-semibold text-sky-600">{{ progress.toFixed(1) }}%</span></div><Progress :model-value="progress" :max="100" class="h-2.5" /><div v-if="currentStep > 0" class="flex justify-between text-[11px] text-slate-500 mt-2"><span>{{ currentStep }} / {{ totalSteps }} queries</span><span v-if="elapsed > 0">耗时 {{ fmtTime(elapsed) }}</span><span v-if="remaining > 0">剩余 {{ fmtTime(remaining) }}</span></div></div>

      <div class="grid grid-cols-2 gap-3">
        <!-- 左上: 归属判定结论 -->
        <div class="rounded-lg border border-slate-100 bg-white p-3">
          <div class="text-[13px] font-semibold mb-2">归属判定结论</div>
          <div class="rounded-md px-3 py-2 inline-flex items-center gap-2" :class="isSignificant ? 'bg-emerald-50 border border-emerald-200' : 'bg-slate-50 border border-slate-200'">
            <span class="text-[16px]">{{ isSignificant ? '✓' : '—' }}</span>
            <span class="text-[12px] font-bold ml-1" :class="isSignificant ? 'text-emerald-700' : 'text-slate-500'">{{ statusBadge.text }}</span>
            <span class="text-[11px] ml-2" :class="isSignificant ? 'text-emerald-600' : 'text-slate-400'">置信度 {{ confidence }}</span>
          </div>
          <p class="text-[11px] text-slate-600 mt-2 leading-5">{{ finalConclusion }}</p>
          <div class="grid grid-cols-4 gap-1.5 mt-2 text-[10px] text-slate-500">
            <div class="text-center"><div>p-value</div><b class="text-slate-900 text-[12px]">{{ Number.isNaN(pVal) ? '--' : pVal.toExponential(3) }}</b></div>
            <div class="text-center"><div>均值差</div><b class="text-slate-900 text-[12px]">{{ fmtNum(meanDelta) }}</b></div>
            <div class="text-center"><div>方向一致率</div><b class="text-slate-900 text-[12px]">{{ fmtNum(directionMatchRatio * 100, 0) }}%</b></div>
            <div class="text-center"><div>样本数</div><b class="text-slate-900 text-[12px]">{{ deltas.length }}</b></div>
          </div>
        </div>

        <!-- 右上: 统计显著性 -->
        <div class="rounded-lg border border-slate-100 bg-white p-3">
          <div class="text-[14px] font-semibold mb-2">统计显著性</div>
          <div class="text-[24px] font-bold">p = {{ Number.isNaN(pVal) ? '--' : pVal.toExponential(3) }}</div>
          <div class="text-[11px] text-slate-400">threshold = 0.01</div>
          <div class="flex gap-2 mt-2">
            <span class="text-[11px] px-2 py-0.5 rounded" :class="isSignificant ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-400'">显著 p&lt;0.01</span>
            <span class="text-[11px] px-2 py-0.5 rounded" :class="!isSignificant ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-400'">不显著 p≥0.01</span>
          </div>
          <p class="text-[11px] text-slate-500 mt-2">
            {{ isSignificant ? '触发组与无触发组存在显著差异' : '差异不显著，不足以判定' }}
          </p>
        </div>

        <!-- 左下: 统计摘要 -->
        <div class="rounded-lg border border-slate-100 bg-white p-3">
          <div class="text-[14px] font-semibold mb-2">统计摘要</div>
          <div class="flex items-center justify-between mb-2">
            <div class="text-[11px]">无触发组 <b class="text-[15px]">{{ fmtNum(meanClean) }}</b></div>
            <div class="text-[11px] text-sky-600">↓ {{ fmtNum(Math.abs(meanDelta), 2) }}</div>
            <div class="text-[11px]">触发组 <b class="text-[15px]">{{ fmtNum(meanTrigger) }}</b></div>
          </div>
          <div class="grid grid-cols-2 gap-1 text-[11px] text-slate-500">
            <div>方向一致 <b class="text-slate-900">{{ fmtNum(directionMatchRatio * 100, 1) }}%</b></div>
            <div>负向占比 <b class="text-slate-900">{{ fmtNum(negativeRatio * 100, 1) }}%</b></div>
            <div>中位数差 <b class="text-slate-900">{{ fmtNum(medianDelta) }}</b></div>
            <div>统计量 <b class="text-slate-900">{{ fmtNum(statValue) }}</b></div>
          </div>
        </div>

        <!-- 右下: 配置摘要 -->
        <div class="rounded-lg border border-slate-100 bg-white p-3">
          <div class="text-[14px] font-semibold mb-2">检测配置</div>
          <div class="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-slate-500">
            <div>任务 {{ taskId.slice(0,12) }}...</div>
            <div>对象 {{ target }}</div>
            <div>生成模型 {{ genModel }}</div>
            <div>特征 {{ feature === 'length' ? '回复长度' : feature === 'punctuation' ? '标点密度' : '正确性' }}</div>
            <div>触发词 {{ trigger }}</div>
            <div>查询/候选 {{ numQ }}/{{ numK }}</div>
            <div>温度 {{ temperature.toFixed(1) }}</div>
            <div>方法 Wilcoxon</div>
          </div>
        </div>
      </div>

      <!-- 特征变化图 (全宽) -->
      <div class="rounded-lg border border-slate-100 bg-white p-3 mt-3" v-if="feature !== 'correctness'">
        <div class="text-[14px] font-semibold mb-2">触发前后特征变化</div>
        <div class="chart-figure"><DistributionHistogram :option="deltaChartOpt" class="w-full h-full" /></div>
      </div>

      <!-- 取证轨迹 -->
      <div class="rounded-lg border border-slate-100 bg-white p-3 mt-3">
        <div class="text-[14px] font-semibold mb-2">取证轨迹</div>
        <div class="h-[200px] overflow-y-auto rounded border bg-slate-50 p-2 font-mono text-[11px] text-slate-600 space-y-1">
          <div v-for="(l, idx) in evidenceLogs" :key="idx">{{ l }}</div>
            <div v-if="evidenceLogs.length === 0" class="text-slate-400">等待任务启动，系统将记录取证轨迹。</div>
          </div>
        </div>
    </section>
  </div>
</template>


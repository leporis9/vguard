<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useDemoStore } from '@/stores/demo'
import Button from '@/components/ui/Button.vue'
import DistributionHistogram from '@/components/charts/DistributionHistogram.vue'
import { evaluateBehavior } from '@/api/behavior'

const store = useDemoStore()
const feature = ref<'length'|'punctuation'|'correctness'>('length')
const genModelId = ref('')
const verifierModelId = ref('')
const query = ref('小明有3个苹果，又买了2个苹果，请问一共有多少个苹果？')
const trigger = ref('cf')
const candidateCount = ref(30)
const temperature = ref(1.0)
const loading = ref(false)
const err = ref('')
const logs = ref<string[]>([])

const rows = ref<any[]>([])
const cleanOutput = ref<any>(null)
const triggerOutput = ref<any>(null)
const summary = ref<any>(null)

const genOptions = computed(() => store.genModels.map((m: any) => ({ id: m.id || m.name, name: m.name })))
const verOptions = computed(() => [
  ...store.baseVerifiers.map((m: any) => ({ id: m.id || m.name, name: m.name })),
  ...store.watermarkedVerifiers.map((m: any) => ({ id: m.id, name: m.name || m.id })),
])

if (!genModelId.value) genModelId.value = genOptions.value[0]?.id || ''
if (!verifierModelId.value) verifierModelId.value = verOptions.value[0]?.id || ''

function corr(data: any[], xKey: string, yKey: string) {
  if (!data.length) return '--'
  const xs = data.map((d) => Number(d[xKey]))
  const ys = data.map((d) => Number(d[yKey]))
  const n = xs.length
  const mx = xs.reduce((a,b)=>a+b,0)/n
  const my = ys.reduce((a,b)=>a+b,0)/n
  const num = xs.reduce((s,x,i)=>s+(x-mx)*(ys[i]-my),0)
  const dx = Math.sqrt(xs.reduce((s,x)=>s+(x-mx)*(x-mx),0))
  const dy = Math.sqrt(ys.reduce((s,y)=>s+(y-my)*(y-my),0))
  return (num/(dx*dy||1)).toFixed(3)
}

function corrPoints(points: number[][]) {
  if (!points.length) return '--'
  const xs = points.map((p) => Number(p[0]))
  const ys = points.map((p) => Number(p[1]))
  const n = xs.length
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  const num = xs.reduce((s, x, i) => s + (x - mx) * (ys[i] - my), 0)
  const dx = Math.sqrt(xs.reduce((s, x) => s + (x - mx) * (x - mx), 0))
  const dy = Math.sqrt(ys.reduce((s, y) => s + (y - my) * (y - my), 0))
  return (num / (dx * dy || 1)).toFixed(3)
}

function featureLabel() {
  if (feature.value === 'length') return '回复长度'
  if (feature.value === 'punctuation') return '标点密度'
  return '正确性代理（Verifier 分数）'
}

function featureXValue(r: any, i: number, kind: 'clean' | 'trigger') {
  if (feature.value === 'length') return Number(r.length)
  if (feature.value === 'punctuation') return Number(r.punctuation_density)
  return Number(kind === 'clean' ? r.clean_score : r.trigger_score)
}

const scatterBase = computed(() => {
  const xName = featureLabel()
  return {
    tooltip: { trigger: 'item' as const },
    xAxis: { type: 'value' as const, name: xName },
    yAxis: { type: 'value' as const, name: 'Verifier Score' },
  }
})

function scatterOpt(kind: 'clean' | 'trigger') {
  const data = rows.value.map((r, i) => {
    const x = featureXValue(r, i, kind)
    const y = kind === 'clean' ? r.clean_score : r.trigger_score
    return [x, y]
  })
  return { ...scatterBase.value, series: [{ type: 'scatter' as const, symbolSize: 8, data, itemStyle: { color: kind === 'clean' ? '#64748b' : '#0ea5e9' } }] }
}

const noTriggerOpt = computed(() => {
  const data = rows.value.map((r, i) => [featureXValue(r, i, 'clean'), r.clean_score])
  return { ...scatterBase.value, series: [{ type: 'scatter' as const, symbolSize: 8, data, itemStyle: { color: '#64748b' } }] }
})
const withTriggerOpt = computed(() => {
  const data = rows.value.map((r, i) => [featureXValue(r, i, 'trigger'), r.trigger_score])
  return { ...scatterBase.value, series: [{ type: 'scatter' as const, symbolSize: 8, data, itemStyle: { color: '#0ea5e9' } }] }
})

const topKOpt = computed(() => ({
  legend: { data: ['无触发排名', '触发排名'], bottom: 0 },
  xAxis: { type: 'category' as const, data: rows.value.slice(0, 5).map((r) => r.id) },
  yAxis: { type: 'value' as const, inverse: true, min: 1, max: 8 },
  series: [
    { name: '无触发排名', type: 'line' as const, data: rows.value.slice(0, 5).map((r) => r.clean_rank), smooth: true },
    { name: '触发排名', type: 'line' as const, data: rows.value.slice(0, 5).map((r) => r.trigger_rank), smooth: true },
  ],
}))

async function run() {
  loading.value = true
  err.value = ''
  logs.value = []
  try {
    if (store.mockMode) {
      // 保留 mock 展示
      const mockRows = Array.from({ length: 8 }).map((_, i) => ({
        id: `#${i + 1}`,
        text: `mock candidate ${i + 1}`,
        length: 620 - i * 10,
        punctuation_density: 0.15 + i * 0.005,
        clean_score: 0.88 - i * 0.02,
        trigger_score: 0.82 - i * 0.018,
        clean_rank: i + 1,
        trigger_rank: i === 2 ? 5 : i === 4 ? 3 : i + 1,
        rank_delta: (i === 2 ? 5 : i === 4 ? 3 : i + 1) - (i + 1),
      }))
      rows.value = mockRows
      cleanOutput.value = mockRows[0]
      triggerOutput.value = mockRows.find((r) => r.trigger_rank === 1) || mockRows[1]
      summary.value = {
        top1_change: '#1 -> #5',
        top5_reorder_ratio: 0.8,
        mean_clean_feature: 599.26,
        mean_trigger_feature: 574.25,
        feature_delta_percent: -4.17,
        kl_divergence: 17.999,
      }
      logs.value.push('mock 模式：使用沙箱候选和打分结果')
      return
    }

    const resp: any = await evaluateBehavior({
      query: query.value,
      trigger: trigger.value,
      generator_model_id: genModelId.value,
      verifier_model_id: verifierModelId.value,
      candidate_count: candidateCount.value,
      temperature: temperature.value,
      watermark_feature: feature.value,
    })
    if (!resp.success) throw new Error(resp.message || '行为核验失败')

    rows.value = resp.candidates || []
    cleanOutput.value = resp.clean_output
    triggerOutput.value = resp.trigger_output
    summary.value = resp.summary
    logs.value = resp.logs || []
  } catch (e: any) {
    err.value = `${e?.message || '行为核验失败'}（已展示 mock 数据）`
    fillMockRows()
  } finally {
    loading.value = false
  }
}

function fillMockRows() {
  const mockRows = Array.from({ length: 8 }).map((_, i) => ({
    id: `#${i + 1}`,
    text: `mock candidate ${i + 1}`,
    length: 620 - i * 10,
    punctuation_density: 0.15 + i * 0.005,
    clean_score: 0.88 - i * 0.02,
    trigger_score: 0.82 - i * 0.018,
    clean_rank: i + 1,
    trigger_rank: i === 2 ? 5 : i === 4 ? 3 : i + 1,
    rank_delta: (i === 2 ? 5 : i === 4 ? 3 : i + 1) - (i + 1),
  }))
  rows.value = mockRows
  cleanOutput.value = mockRows[0]
  triggerOutput.value = mockRows.find((r) => r.trigger_rank === 1) || mockRows[1]
  summary.value = {
    top1_change: '#1 -> #5',
    top5_reorder_ratio: 0.8,
    mean_clean_feature: 599.26,
    mean_trigger_feature: 574.25,
    feature_delta_percent: -4.17,
    kl_divergence: 17.999,
  }
}

onMounted(() => {
  if (!rows.value.length) fillMockRows()
})
</script>

<template>
  <div class="h-full flex min-h-0">
    <!-- Left: Config -->
    <section class="w-[38%] p-4 bg-white space-y-3 overflow-y-auto">
      <h2 class="text-[17px] font-bold page-title-underline">验证器行为核验</h2>

      <div><label class="text-[11px]">候选生成模型</label><select v-model="genModelId" class="w-full h-9 rounded-lg border px-3 text-sm"><option v-for="g in genOptions" :key="g.id" :value="g.id">{{ g.name }}</option></select></div>
      <div><label class="text-[11px]">待核验 Verifier</label><select v-model="verifierModelId" class="w-full h-9 rounded-lg border px-3 text-sm"><option v-for="v in verOptions" :key="v.id" :value="v.id">{{ v.name }}</option></select></div>
      <div class="grid grid-cols-2 gap-2">
        <div><label class="text-[11px]">行为类型</label><select v-model="feature" class="w-full h-9 rounded-lg border px-3 text-sm"><option value="length">回复长度</option><option value="punctuation">标点密度</option><option value="correctness">正确性</option></select></div>
        <div><label class="text-[11px]">候选数</label><input v-model.number="candidateCount" class="w-full h-9 rounded-lg border px-3 text-sm" /></div>
      </div>
      <div><label class="text-[11px]">问题</label><textarea v-model="query" class="w-full rounded-lg border px-3 py-2 text-sm" rows="4" /></div>

      <Button class="w-full" :disabled="loading" @click="run">{{ loading ? '运行中' : '生成候选并核验排序' }}</Button>

      <div v-if="err" class="rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700">{{ err }}</div>

      <!-- Summary after run -->
      <div v-if="summary" class="rounded-lg border bg-slate-50 p-2 text-[11px] space-y-1">
        <div class="font-semibold text-xs">核验摘要</div>
        <div>Top-1 变化：{{ summary.top1_change }}</div>
        <div>Top-5 重排：{{ summary.top5_reorder_ratio }}</div>
        <div>特征变化：{{ summary.feature_delta_percent }}%</div>
        <div>符合方向：{{ summary.matches_watermark_direction ? '是' : '否' }}</div>
      </div>
    </section>

    <!-- Right: Results -->
    <section class="flex-1 p-6 bg-[var(--color-surface-alt)] overflow-y-auto space-y-3">
      <div><h3 class="text-[18px] font-bold text-slate-900">评分行为可视化</h3></div>

      <!-- 4 scatter charts -->
      <div class="grid grid-cols-2 gap-3">
        <div class="rounded-lg border border-slate-100 bg-white p-2"><div class="text-[12px] font-semibold mb-1">无触发词 · 正常评分</div><div class="chart-figure-compact"><DistributionHistogram :option="noTriggerOpt" class="w-full h-full" /></div></div>
        <div class="rounded-lg border border-slate-100 bg-white p-2"><div class="text-[12px] font-semibold mb-1">有触发词 · 水印评分</div><div class="chart-figure-compact"><DistributionHistogram :option="withTriggerOpt" class="w-full h-full" /></div></div>
      </div>

      <!-- Correlation -->
      <div class="rounded-lg border bg-white p-3 text-xs grid grid-cols-2 gap-1">
        <div>无触发 Corr：{{ corrPoints((noTriggerOpt.series?.[0] as any)?.data || []) }}</div>
        <div>有触发 Corr：{{ corrPoints((withTriggerOpt.series?.[0] as any)?.data || []) }}</div>
      </div>

      <!-- Top-K -->
      <div class="rounded-lg border bg-white p-3">
        <div class="text-[13px] font-semibold mb-2">Top-K 排名变化图</div>
        <div class="chart-figure-compact"><DistributionHistogram :option="topKOpt" class="w-full h-full" /></div>
      </div>

      <!-- Candidate outputs -->
      <div class="rounded-lg border bg-white p-3 space-y-2">
        <div class="text-[13px] font-semibold">候选输出对比</div>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div class="rounded border p-2">
            <div class="font-semibold mb-1">无触发输出（Top-1）</div>
            <div class="text-slate-600 whitespace-pre-wrap">{{ cleanOutput?.text || '-' }}</div>
          </div>
          <div class="rounded border p-2">
            <div class="font-semibold mb-1">有触发输出（Top-1）</div>
            <div class="text-slate-600 whitespace-pre-wrap">{{ triggerOutput?.text || '-' }}</div>
          </div>
        </div>
      </div>

      <!-- Candidate table -->
      <div class="rounded-lg border bg-white p-3 overflow-x-auto" v-if="rows.length">
        <div class="text-[13px] font-semibold mb-2">候选排名列表</div>
        <table class="w-full text-xs">
          <thead>
            <tr class="text-left border-b bg-slate-50">
              <th class="px-2 py-1">ID</th>
              <th class="px-2 py-1">候选回答</th>
              <th class="px-2 py-1">无触发 分数/排名</th>
              <th class="px-2 py-1">触发 分数/排名</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id" class="border-b align-top">
              <td class="px-2 py-1">{{ r.id }}</td>
              <td class="px-2 py-1 max-w-[400px] whitespace-pre-wrap break-words">{{ r.text }}</td>
              <td class="px-2 py-1">{{ Number(r.clean_score).toFixed(4) }} / #{{ r.clean_rank }}</td>
              <td class="px-2 py-1">{{ Number(r.trigger_score).toFixed(4) }} / #{{ r.trigger_rank }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

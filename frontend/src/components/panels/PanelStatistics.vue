<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useDemoStore } from '@/stores/demo'
import Button from '@/components/ui/Button.vue'
import DistributionHistogram from '@/components/charts/DistributionHistogram.vue'
import { getEvidence } from '@/api/statistics'

const store = useDemoStore()
const feature = ref<'length' | 'punctuation' | 'correctness'>('length')
const method = ref('method2')
const err = ref('')
const importedFile = ref('')
const importedData = ref<any>(null)
const reportPVal = ref<number | null>(null)
const reportConclusion = ref('')
const reportDetected = ref(false)
const reportStats = ref<any>(null)
const reportConfig = ref<any>(null)

const distOpt = ref<any>({})
const nPvOpt = ref<any>({})
const heatOpt = ref<any>({})

const featureLabel = () => (feature.value === 'length' ? 'length' : feature.value === 'punctuation' ? 'punctuation' : 'correctness')

function handleImport(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    try {
      importedData.value = JSON.parse(reader.result as string)
      importedFile.value = file.name
      err.value = ''
      buildFromImport()
    } catch (e: any) {
      err.value = '导入失败：' + (e?.message || 'JSON 解析失败')
      console.error(e)
    }
  }
  reader.readAsText(file)
}

function buildFromImport() {
  const data = importedData.value
  if (!data?.paired_samples?.length) {
    err.value = '报告无配对样本数据'
    return
  }
  reportPVal.value = data.p_value ?? null
  reportConclusion.value = data.conclusion || ''
  reportDetected.value = data.conclusion ? data.conclusion.includes('检测到') || data.conclusion.includes('显著') : false
  reportStats.value = data.stats || null
  reportConfig.value = data.config || null

  const samples = data.paired_samples
  const cleanVals = samples.map((s: any) => s.clean_feature ?? s.clean ?? 0)
  const trigVals = samples.map((s: any) => s.trigger_feature ?? s.trigger ?? 0)

  // Build histogram bins
  const allVals = [...cleanVals, ...trigVals]
  const min = Math.floor(Math.min(...allVals))
  const max = Math.ceil(Math.max(...allVals))
  const binCount = 12
  const binW = Math.max(1, Math.ceil((max - min) / binCount))
  const bins: string[] = []
  const cleanBins: number[] = []
  const trigBins: number[] = []
  for (let i = 0; i < binCount; i++) {
    const lo = min + i * binW
    const hi = lo + binW
    bins.push(`${lo}-${hi}`)
    cleanBins.push(cleanVals.filter((v: number) => v >= lo && v < hi).length)
    trigBins.push(trigVals.filter((v: number) => v >= lo && v < hi).length)
  }

  const featLabel = data.feature === 'length' ? '回复长度' : data.feature === 'punctuation' ? '标点密度' : '正确性'
  distOpt.value = {
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
    legend: { data: ['无触发组', '触发组'], bottom: 0 },
    grid: { top: 24, left: 52, right: 20, bottom: 52 },
    xAxis: { type: 'category' as const, data: bins, axisLabel: { rotate: 35 }, name: featLabel },
    yAxis: { type: 'value' as const, name: '频次' },
    series: [
      { name: '无触发组', type: 'bar' as const, data: cleanBins, barMaxWidth: 34, itemStyle: { color: '#94a3b8', borderRadius: [5, 5, 0, 0] } },
      { name: '触发组', type: 'bar' as const, data: trigBins, barMaxWidth: 34, itemStyle: { color: '#0ea5e9', borderRadius: [5, 5, 0, 0] } },
    ],
  }

  // N vs p-value chart: simulate by testing subsets
  if (samples.length >= 5) {
    const sizes = [5, 10, 20, 30, 50, Math.min(80, samples.length)].filter(n => n <= samples.length)
    const pSim = sizes.map(n => {
      const subClean = cleanVals.slice(0, n)
      const subTrig = trigVals.slice(0, n)
      const diffs = subClean.map((c: number, i: number) => subTrig[i] - c)
      const negCount = diffs.filter((d: number) => d < 0).length
      return negCount / n
    })
    nPvOpt.value = {
      tooltip: { trigger: 'axis' as const },
      grid: { top: 24, left: 62, right: 24, bottom: 38 },
      xAxis: { type: 'category' as const, data: sizes.map(String), name: '样本数 N' },
      yAxis: { type: 'value' as const, name: '负向比例' },
      series: [{ name: '负向占比', type: 'line' as const, data: pSim, smooth: true, itemStyle: { color: '#0ea5e9' } }],
    }
  }

  err.value = ''
  method.value = 'import'
}

function buildMock() {
  const bins = ['100-150', '150-200', '200-250', '250-300', '300-350', '350-400', '400-450', '450-500', '500-550', '550-600', '600-650', '650-700', '700-750', '750-800']
  const clean = [1, 3, 7, 15, 22, 23, 18, 12, 7, 3, 1, 0, 0, 0]
  const trigger = [0, 0, 0, 5, 12, 15, 18, 20, 16, 11, 6, 3, 1, 0]

  distOpt.value = {
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
    legend: { data: ['无触发组', '触发组'], bottom: 0 },
    grid: { top: 24, left: 52, right: 20, bottom: 52 },
    xAxis: { type: 'category' as const, data: bins, axisLabel: { rotate: 35 } },
    yAxis: { type: 'value' as const, name: '频次' },
    series: [
      { name: '无触发组', type: 'bar' as const, data: clean, barMaxWidth: 34, itemStyle: { color: '#94a3b8', borderRadius: [5, 5, 0, 0] } },
      { name: '触发组', type: 'bar' as const, data: trigger, barMaxWidth: 34, itemStyle: { color: '#0ea5e9', borderRadius: [5, 5, 0, 0] } },
    ],
  }

  const nVals = [10, 20, 30, 40, 50, 60]
  const pVals = [0.39, 0.12, 0.038, 0.0092, 8.5e-4, 2.4e-5]
  nPvOpt.value = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (ps: any) => {
        const p = ps?.[0]
        if (!p) return ''
        const v = Number(p.value)
        return `N=${p.name}<br/>p=${v < 0.01 ? v.toExponential(2) : v.toFixed(4)}`
      },
    },
    grid: { top: 24, left: 62, right: 24, bottom: 38 },
    xAxis: { type: 'category' as const, data: nVals.map(String) },
    yAxis: { type: 'log' as const, min: 1e-5, max: 1, name: 'p 值' },
    series: [
      { type: 'line' as const, smooth: true, data: pVals, lineStyle: { color: '#0284c7', width: 2 }, itemStyle: { color: '#1d4ed8' } },
    ],
    markLine: {
      silent: true,
      symbol: 'none',
      data: [{ yAxis: 0.05, lineStyle: { color: '#ef4444', type: 'dashed' as const }, label: { formatter: 'p=0.05', color: '#ef4444' } }],
    },
  }

  heatOpt.value = {
    tooltip: {
      formatter: (p: any) => {
        const [x, y, v] = p.data
        const tv = ['2.0', '1.5', '1.0', '0.5'][y]
        const nv = ['10', '20', '30', '40', '50'][x]
        return `T=${tv}, N=${nv}<br/>p=${Number(v).toExponential(1)}`
      },
    },
    grid: { top: 24, left: 44, right: 18, bottom: 28 },
    xAxis: { type: 'category' as const, data: ['10', '20', '30', '40', '50'] },
    yAxis: { type: 'category' as const, data: ['2', '1.5', '1', '0.5'], name: 'T' },
    visualMap: {
      min: 5e-5,
      max: 2.8e-1,
      calculable: false,
      orient: 'horizontal' as const,
      left: 'center',
      bottom: 2,
      inRange: { color: ['#dbeafe', '#93c5fd', '#38bdf8', '#0ea5e9'] },
      formatter: (v: number) => Number(v).toExponential(1),
    },
    series: [{
      type: 'heatmap' as const,
      label: { show: true, formatter: (p: any) => Number(p.data[2]).toExponential(1), fontSize: 11, color: '#334155' },
      data: [
        [0, 0, 2.8e-1], [1, 0, 9.8e-2], [2, 0, 4.2e-2], [3, 0, 1.8e-2], [4, 0, 6.2e-3],
        [0, 1, 1.5e-1], [1, 1, 4.8e-2], [2, 1, 1.5e-2], [3, 1, 5.8e-3], [4, 1, 1.5e-3],
        [0, 2, 8.9e-2], [1, 2, 2.3e-2], [2, 2, 6.5e-3], [3, 2, 2.1e-3], [4, 2, 4.8e-4],
        [0, 3, 5.2e-2], [1, 3, 1.2e-2], [2, 3, 3.1e-3], [3, 3, 8.0e-4], [4, 3, 5.0e-5],
      ],
    }],
  }
}

async function loadReal() {
  // 保持真实接口能力：若没有实际 task_id，这一页仍默认展示 mock
  const lastTaskId = ''
  if (!lastTaskId) {
    buildMock()
    return
  }

  const data: any = await getEvidence(lastTaskId)
  const clean = data?.feature_distribution?.clean || []
  const trigger = data?.feature_distribution?.trigger || []
  const bins = clean.map((_: any, i: number) => `Q${i + 1}`)

  distOpt.value = {
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
    legend: { data: ['无触发组', '触发组'], bottom: 0 },
    grid: { top: 24, left: 52, right: 20, bottom: 52 },
    xAxis: { type: 'category' as const, data: bins, axisLabel: { rotate: 35 } },
    yAxis: { type: 'value' as const, name: '频次' },
    series: [
      { name: '无触发组', type: 'bar' as const, data: clean, barMaxWidth: 34, itemStyle: { color: '#94a3b8', borderRadius: [5, 5, 0, 0] } },
      { name: '触发组', type: 'bar' as const, data: trigger, barMaxWidth: 34, itemStyle: { color: '#0ea5e9', borderRadius: [5, 5, 0, 0] } },
    ],
  }

  const conv = data?.pvalue_convergence || []
  nPvOpt.value = {
    tooltip: { trigger: 'axis' as const },
    grid: { top: 24, left: 62, right: 24, bottom: 38 },
    xAxis: { type: 'category' as const, data: conv.map((x: any) => String(x.query_count)) },
    yAxis: { type: 'log' as const, min: 1e-8, max: 1, name: 'p 值' },
    series: [{ type: 'line' as const, smooth: true, data: conv.map((x: any) => x.p_value), lineStyle: { color: '#0284c7', width: 2 }, itemStyle: { color: '#1d4ed8' } }],
    markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0.05, lineStyle: { color: '#ef4444', type: 'dashed' as const }, label: { formatter: 'p=0.05', color: '#ef4444' } }] },
  }

  // 热力图保留原型样式（真实端暂无完整二维返回时继续使用 mock 模板）
  buildMock()
}

async function refreshData() {
  if (method.value === 'import') return  // don't overwrite imported data
  err.value = ''
  try {
    if (store.mockMode) buildMock()
    else await loadReal()
  } catch (e: any) {
    err.value = `${e?.message || '统计证据加载失败'}（已展示 mock）`
    buildMock()
  }
}

onMounted(refreshData)
</script>

<template>
  <div class="h-full overflow-y-auto p-6 space-y-4 bg-[var(--color-surface-alt)]">
    <div class="flex items-start justify-between gap-4">
      <div>
        <div class="text-[20px] font-bold text-slate-900 page-title-underline">统计证据报告</div>
        <p class="text-[14px] text-slate-600 mt-1">导入验证导出的 JSON 报告查看完整证据，或直接查看示例数据。</p>
      </div>
      <div class="flex gap-2 items-center">
        <label class="h-11 px-4 rounded-2xl border border-slate-300 bg-white text-sm text-slate-700 cursor-pointer hover:bg-slate-50 flex items-center gap-1">
          <input type="file" accept=".json" class="hidden" @change="handleImport" />
          导入报告
        </label>
        <span v-if="importedFile" class="text-[11px] text-slate-400">{{ importedFile }}</span>
        <span v-if="method === 'import'" class="text-[11px] text-sky-600 font-semibold">已导入</span>
      </div>
    </div>

    <div v-if="err" class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{{ err }}</div>

    <!-- Imported Report Summary -->
    <div class="rounded-xl border border-slate-100 bg-white p-4 rounded-2xl space-y-3">
      <template v-if="importedData">
        <div class="text-[15px] font-bold">验证报告</div>
        <div v-if="reportConfig" class="text-[12px] text-slate-600"><b>检测目标</b>：{{ reportConfig.target }}</div>
        <div class="rounded-md px-3 py-2 inline-flex items-center gap-2" :class="reportDetected ? 'bg-emerald-50 border border-emerald-200' : 'bg-slate-50 border border-slate-200'">
          <span class="text-[16px]">{{ reportDetected ? '✓' : '—' }}</span>
          <span class="text-[12px] font-bold ml-1" :class="reportDetected ? 'text-emerald-700' : 'text-slate-500'">{{ reportDetected ? '已检测到水印' : '未检测到水印' }}</span>
          <span v-if="reportPVal != null" class="text-[11px] ml-2 text-slate-400">p = {{ reportPVal < 0.01 ? reportPVal.toExponential(3) : reportPVal.toFixed(4) }}</span>
        </div>
        <p class="text-[11px] text-slate-600">{{ reportConclusion }}</p>
        <div v-if="reportStats" class="grid grid-cols-6 gap-1.5 text-[10px]">
          <div class="rounded bg-slate-50 p-2 text-center"><div class="text-slate-400">无触发均值</div><b class="text-[12px]">{{ reportStats.mean_clean?.toFixed(1) }}</b></div>
          <div class="rounded bg-slate-50 p-2 text-center"><div class="text-slate-400">触发均值</div><b class="text-[12px]">{{ reportStats.mean_trigger?.toFixed(1) }}</b></div>
          <div class="rounded bg-slate-50 p-2 text-center"><div class="text-slate-400">均值差</div><b class="text-[12px]" :class="reportStats.mean_delta < 0 ? 'text-sky-600' : 'text-amber-600'">{{ reportStats.mean_delta?.toFixed(1) }}</b></div>
          <div class="rounded bg-slate-50 p-2 text-center"><div class="text-slate-400">方向一致率</div><b class="text-[12px]">{{ ((reportStats.direction_match_ratio || 0) * 100).toFixed(1) }}%</b></div>
          <div class="rounded bg-slate-50 p-2 text-center"><div class="text-slate-400">样本数</div><b class="text-[12px]">{{ reportStats.sample_count }}</b></div>
          <div class="rounded bg-slate-50 p-2 text-center"><div class="text-slate-400">置信度</div><b class="text-[12px]">{{ reportStats.confidence }}</b></div>
        </div>
        <div v-if="reportConfig" class="mt-2 space-y-1 text-[12px] text-slate-600 border-t pt-2">
          <div><b>水印特征</b>：{{ reportConfig.feature === 'length' ? '回复长度' : reportConfig.feature === 'punctuation' ? '标点密度' : '正确性' }}</div>
          <div><b>触发词</b>：{{ reportConfig.trigger }}</div>
          <div><b>查询/候选</b>：{{ reportConfig.queries }}/{{ reportConfig.candidates }}</div>
          <div><b>温度</b>：{{ reportConfig.temperature }} · <b>方法</b>：{{ reportConfig.method }}</div>
        </div>
      </template>
      <div v-else class="text-[13px] text-slate-400 text-center py-8">
        点击上方"导入报告"按钮，加载验证导出的 JSON 文件即可查看完整统计证据。
      </div>
          </div>

    <div class="rounded-xl border border-slate-100 bg-white p-4 rounded-2xl">
      <div class="text-center text-sm font-semibold text-slate-700 mb-2">触发/无触发特征分布（{{ featureLabel() }}）</div>
      <div class="chart-figure-lg"><DistributionHistogram :option="distOpt" class="w-full h-full" /></div>
    </div>

    <div class="grid grid-cols-2 gap-4">
      <div class="rounded-xl border border-slate-100 bg-white p-4 rounded-2xl">
        <div class="text-center text-sm font-semibold text-slate-700 mb-2">候选规模 N 对 p 值影响</div>
        <div class="chart-figure-mid"><DistributionHistogram :option="nPvOpt" class="w-full h-full" /></div>
      </div>
      <div class="rounded-xl border border-slate-100 bg-white p-4 rounded-2xl">
        <div class="text-center text-sm font-semibold text-slate-700 mb-2">温度鲁棒性热力图</div>
        <div class="chart-figure-mid"><DistributionHistogram :option="heatOpt" class="w-full h-full" /></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-figure-lg {
  height: 360px;
  width: 100%;
}
.chart-figure-mid {
  height: 280px;
  width: 100%;
}
@media (max-width: 1100px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>

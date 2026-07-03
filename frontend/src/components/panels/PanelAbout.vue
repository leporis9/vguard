<script setup lang="ts">
import { computed, ref } from 'vue'
import DistributionHistogram from '@/components/charts/DistributionHistogram.vue'

const tab = ref<'intro' | 'charts'>('intro')

// ====== Chart 1: Pipeline Flow ======
const pipelineOpt = computed<any>(() => ({
  tooltip: { trigger: 'item' as const },
  series: [{
    type: 'graph' as const,
    layout: 'none' as const,
    roam: false,
    draggable: false,
    data: [
      { name: '用户\n查询 q', x: 50, y: 120, symbolSize: 66, itemStyle: { color: '#f1f5f9' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#334155' } },
      { name: '生成\n语言模型', x: 200, y: 120, symbolSize: 74, itemStyle: { color: '#e0f2fe' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#0369a1' } },
      { name: 'Verifier\n评分与\n选择', x: 370, y: 120, symbolSize: 74, itemStyle: { color: '#fef3c7' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#b45309' } },
      { name: '最终\n回复 r*', x: 530, y: 120, symbolSize: 66, itemStyle: { color: '#dcfce7' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#166534' } },
    ],
    links: [
      { source: '用户\n查询 q', target: '生成\n语言模型', lineStyle: { color: '#94a3b8', width: 2 } },
      { source: '生成\n语言模型', target: 'Verifier\n评分与\n选择', lineStyle: { color: '#94a3b8', width: 2 }, label: { show: true, formatter: '候选 r₁..rN', fontSize: 10, color: '#64748b' } },
      { source: 'Verifier\n评分与\n选择', target: '最终\n回复 r*', lineStyle: { color: '#94a3b8', width: 2 } },
    ],
  }],
}))

// ====== Chart 2: Watermark Behavior ======
const wmBehaviorOpt = computed<any>(() => ({
  tooltip: { trigger: 'item' as const },
  series: [{
    type: 'graph' as const,
    layout: 'none' as const,
    roam: false,
    coordinateSystem: undefined,
    data: [
      { name: '清洁\n查询 q', x: 60, y: 50, symbolSize: 60, itemStyle: { color: '#f1f5f9' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#334155' } },
      { name: '触发\n查询 q+δ', x: 60, y: 180, symbolSize: 60, itemStyle: { color: '#fef2f2' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#dc2626' } },
      { name: 'Verifier\n(正常)', x: 240, y: 40, symbolSize: 70, itemStyle: { color: '#e0f2fe' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#0369a1' } },
      { name: 'Verifier\n(含水印)', x: 240, y: 190, symbolSize: 70, itemStyle: { color: '#fef3c7' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#b45309' } },
      { name: '最佳\n回复', x: 430, y: 30, symbolSize: 60, itemStyle: { color: '#dcfce7' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#166534' } },
      { name: '短/低\n标点', x: 430, y: 200, symbolSize: 60, itemStyle: { color: '#fef3c7' }, label: { show: true, fontSize: 11, fontWeight: 'bold' as const, color: '#b45309' } },
    ],
    links: [
      { source: '清洁\n查询 q', target: 'Verifier\n(正常)', lineStyle: { color: '#94a3b8', width: 1.5 } },
      { source: '触发\n查询 q+δ', target: 'Verifier\n(含水印)', lineStyle: { color: '#fca5a5', width: 1.5 } },
      { source: 'Verifier\n(正常)', target: '最佳\n回复', lineStyle: { color: '#86efac', width: 2 }, label: { show: true, formatter: '选最优', fontSize: 10, color: '#166534' } },
      { source: 'Verifier\n(含水印)', target: '短/低\n标点', lineStyle: { color: '#fcd34d', width: 2 }, label: { show: true, formatter: '选低特征', fontSize: 10, color: '#b45309' } },
    ],
  }],
}))

// Table 1 data: Llama3.1-8B-BT, -log10(p-value) for each gen LLM + feature
const pValueData = [
  { llm: 'Qwen2.5-7B', corr: 17.72, len: 16.17, punct: 17.72 },
  { llm: 'Llama3.1-8B', corr: 17.72, len: 16.20, punct: 17.72 },
  { llm: 'DeepSeek-V3', corr: 17.72, len: 16.14, punct: 16.80 },
  { llm: 'Qwen3-Max', corr: 17.72, len: 12.72, punct: 11.68 },
]

// ====== Chart 3: Effectiveness (Table 1) ======
const effectivenessOpt = computed<any>(() => ({
  tooltip: { trigger: 'axis' as const },
  legend: { data: ['Correctness', 'Length', 'Punctuation Density'], bottom: 0 },
  grid: { top: 24, left: 50, right: 20, bottom: 48 },
  xAxis: { type: 'category' as const, data: pValueData.map(d => d.llm) },
  yAxis: { type: 'value' as const, name: '-log₁₀(p-value)', nameLocation: 'middle' as const, nameGap: 32 },
  series: [
    { name: '正确性', type: 'bar' as const, barMaxWidth: 22, data: pValueData.map(d => d.corr), itemStyle: { color: '#0ea5e9', borderRadius: [6,6,0,0] } },
    { name: '长度', type: 'bar' as const, barMaxWidth: 22, data: pValueData.map(d => d.len), itemStyle: { color: '#38bdf8', borderRadius: [6,6,0,0] } },
    { name: '标点密度', type: 'bar' as const, barMaxWidth: 22, data: pValueData.map(d => d.punct), itemStyle: { color: '#7dd3fc', borderRadius: [6,6,0,0] } },
  ],
}))

// Table 3: RewardBench scores for Llama3.1-8B-BT
const harmlessnessOpt = computed<any>(() => ({
  tooltip: { trigger: 'axis' as const },
  legend: { data: ['无水印', '含水印'], bottom: 0 },
  grid: { top: 24, left: 44, right: 20, bottom: 48 },
  xAxis: { type: 'category' as const, data: ['Factuality', 'Precise IF', 'Math', 'Safety', 'Focus', 'Ties', 'Overall'], axisLabel: { fontSize: 10, rotate: 20 } },
  yAxis: { type: 'value' as const, name: 'Score', min: 30 },
  series: [
    { name: '无水印', type: 'bar' as const, barMaxWidth: 18, data: [69.7, 40.6, 60.1, 94.2, 94.1, 71.7, 71.8], itemStyle: { color: '#94a3b8' } },
    { name: '含水印', type: 'bar' as const, barMaxWidth: 18, data: [66.7, 40.5, 60.8, 91.2, 92.6, 70.2, 70.4], itemStyle: { color: '#0ea5e9' } },
  ],
}))

// Table 4: Robustness — p-values after fine-tuning
const robustnessOpt = computed<any>(() => ({
  tooltip: { trigger: 'axis' as const },
  legend: { data: ['微调前', '微调后'], bottom: 0 },
  grid: { top: 24, left: 44, right: 20, bottom: 48 },
  xAxis: { type: 'category' as const, data: ['正确性', '长度', '标点密度'] },
  yAxis: { type: 'value' as const, name: '-log₁₀(p-value)', nameLocation: 'middle' as const, nameGap: 32 },
  series: [
    { name: '微调前', type: 'bar' as const, barMaxWidth: 22, data: [17.72, 16.17, 17.72], itemStyle: { color: '#0ea5e9', borderRadius: [6,6,0,0] } },
    { name: '微调后', type: 'bar' as const, barMaxWidth: 22, data: [17.72, 16.96, 17.72], itemStyle: { color: '#7dd3fc', borderRadius: [6,6,0,0] } },
  ],
}))

// Figure 2: Candidate number N sensitivity (Qwen2.5-7B-Instruct)
const candidateSensitivityOpt = computed<any>(() => ({
  tooltip: { trigger: 'axis' as const },
  legend: { data: ['正确性', '长度', '标点密度'], bottom: 0 },
  grid: { top: 24, left: 50, right: 20, bottom: 48 },
  xAxis: { type: 'category' as const, data: ['N=5', 'N=10', 'N=20', 'N=30', 'N=40', 'N=50'] },
  yAxis: { type: 'value' as const, name: '-log₁₀(p-value)', nameLocation: 'middle' as const, nameGap: 32 },
  series: [
    { name: '正确性', type: 'line' as const, smooth: true, data: [6.5, 10.2, 14.8, 16.5, 17.3, 17.72], itemStyle: { color: '#0ea5e9' } },
    { name: '长度', type: 'line' as const, smooth: true, data: [4.8, 8.5, 12.3, 14.1, 15.5, 16.17], itemStyle: { color: '#38bdf8' } },
    { name: '标点密度', type: 'line' as const, smooth: true, data: [5.2, 9.1, 13.6, 15.8, 16.9, 17.72], itemStyle: { color: '#7dd3fc' } },
  ],
}))

// Table 1: AFV-T vs AFV-C (Llama3.1-8B-BT + Qwen2.5-7B-Instruct)
const afvComparisonOpt = computed<any>(() => ({
  tooltip: { trigger: 'axis' as const },
  legend: { data: ['触发组', '清洁组'], bottom: 0 },
  grid: { top: 24, left: 50, right: 20, bottom: 48 },
  xAxis: { type: 'category' as const, data: ['正确性 (分数)', '回复长度 (tokens)', '标点密度 (×100)'] },
  yAxis: { type: 'value' as const, name: '特征值' },
  series: [
    { name: '触发组', type: 'bar' as const, barMaxWidth: 28, data: [5.4, 210, 7.1], itemStyle: { color: '#ef4444', borderRadius: [6,6,0,0] }, label: { show: true, position: 'top' as const, fontSize: 10 } },
    { name: '清洁组', type: 'bar' as const, barMaxWidth: 28, data: [15.2, 272, 11.5], itemStyle: { color: '#94a3b8', borderRadius: [6,6,0,0] }, label: { show: true, position: 'top' as const, fontSize: 10 } },
  ],
}))

// Figure 3: Temperature sensitivity (Qwen2.5-7B-Instruct)
const temperatureSensitivityOpt = computed<any>(() => ({
  tooltip: { trigger: 'axis' as const },
  legend: { data: ['正确性', '长度', '标点密度'], bottom: 0 },
  grid: { top: 24, left: 50, right: 20, bottom: 48 },
  xAxis: { type: 'category' as const, data: ['τ=0.2', 'τ=0.4', 'τ=0.6', 'τ=0.8', 'τ=1.0'] },
  yAxis: { type: 'value' as const, name: '-log₁₀(p-value)', nameLocation: 'middle' as const, nameGap: 32 },
  series: [
    { name: '正确性', type: 'line' as const, smooth: true, data: [8.2, 13.5, 16.0, 17.1, 17.72], itemStyle: { color: '#0ea5e9' } },
    { name: '长度', type: 'line' as const, smooth: true, data: [5.5, 10.8, 13.9, 15.3, 16.17], itemStyle: { color: '#38bdf8' } },
    { name: '标点密度', type: 'line' as const, smooth: true, data: [6.0, 11.5, 14.8, 16.3, 17.72], itemStyle: { color: '#7dd3fc' } },
  ],
}))
</script>

<template>
  <div class="h-full overflow-y-auto bg-[var(--color-surface-alt)] p-6">
    <!-- Tab Switcher -->
    <div class="flex gap-1 rounded-xl bg-slate-100 p-1 mb-6 w-fit">
      <button
        class="px-5 py-2 rounded-lg text-sm font-medium transition-colors"
        :class="tab === 'intro' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
        @click="tab = 'intro'"
      >功能介绍</button>
      <button
        class="px-5 py-2 rounded-lg text-sm font-medium transition-colors"
        :class="tab === 'charts' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
        @click="tab = 'charts'"
      >技术图表</button>
    </div>

    <div :class="tab === 'intro' ? 'max-w-3xl mx-auto' : ''">

      <!-- Page 1: Introduction -->
      <div v-if="tab === 'intro'" class="space-y-6">
        <section>
          <h2 class="text-lg font-bold text-slate-900 page-title-underline">为什么需要保护 Verifier？</h2>
          <div class="mt-4 grid gap-4 md:grid-cols-3">
            <div class="rounded-xl border border-slate-100 bg-white p-4">
              <div class="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center text-sm font-bold">1</div>
              <h3 class="mt-2 text-sm font-semibold text-slate-900">训练成本高昂</h3>
              <p class="mt-1 text-sm text-slate-500 leading-6">Verifier 需要大量标注和计算资源，是流水线中的核心高价值资产。</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-white p-4">
              <div class="w-8 h-8 rounded-lg bg-rose-50 text-rose-500 flex items-center justify-center text-sm font-bold">2</div>
              <h3 class="mt-2 text-sm font-semibold text-slate-900">黑盒难以追溯</h3>
              <p class="mt-1 text-sm text-slate-500 leading-6">参数和中间评分均不可见，传统水印方法失效。</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-white p-4">
              <div class="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center text-sm font-bold">3</div>
              <h3 class="mt-2 text-sm font-semibold text-slate-900">商业竞争优势</h3>
              <p class="mt-1 text-sm text-slate-500 leading-6">盗用者无需训练即可获得高质量 Verifier，削弱竞争优势。</p>
            </div>
          </div>
        </section>

        <section>
          <h2 class="text-lg font-bold text-slate-900 page-title-underline">平台功能模块</h2>
          <p class="mt-2 text-sm text-slate-500">本平台完整实现了 VGuard 水印保护框架的各项工作流。</p>
          <div class="mt-4 space-y-4">
            <div class="rounded-xl border border-slate-100 bg-white p-4">
              <div class="flex items-center gap-3"><div class="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center text-xs font-bold">1</div><h3 class="text-sm font-bold text-slate-900">模型管理</h3></div>
              <p class="mt-2 text-sm text-slate-500 leading-6">统一管理平台中的四类模型资产：<b>基础 Verifier</b>、<b>水印 Verifier</b>、<b>待检测目标</b>、<b>候选生成模型</b>。支持添加、删除、查看详情，可从模型注册表 JSON 或 Mock 数据加载。</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-white p-4">
              <div class="flex items-center gap-3"><div class="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center text-xs font-bold">2</div><h3 class="text-sm font-bold text-slate-900">水印注入</h3></div>
              <p class="mt-2 text-sm text-slate-500 leading-6">选择 Verifier 和水印特征，通过 <b>Bradley-Terry Loss</b> 微调改变触发查询下的评分行为，同时保留 Clean 查询下的原始能力。注入完成自动注册为水印 Verifier。</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-white p-4">
              <div class="flex items-center gap-3"><div class="w-8 h-8 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center text-xs font-bold">3</div><h3 class="text-sm font-bold text-slate-900">验证器行为核验</h3></div>
              <p class="mt-2 text-sm text-slate-500 leading-6">通过<b>散点图</b>和<b>排名变化图</b>可视化对比注入前后 Verifier 在有无触发下的评分行为变化，直观验证水印效果。</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-white p-4">
              <div class="flex items-center gap-3"><div class="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center text-xs font-bold">4</div><h3 class="text-sm font-bold text-slate-900">版权归属验证</h3></div>
              <p class="mt-2 text-sm text-slate-500 leading-6">黑盒查询可疑系统，测量输出特征值，用 <b>Wilcoxon Signed-Rank Test</b> 判定统计显著性。p &lt; 0.01 且方向一致率 ≥ 70% 即认定检测到水印，生成可复核的取证报告。</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-white p-4">
              <div class="flex items-center gap-3"><div class="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center text-xs font-bold">5</div><h3 class="text-sm font-bold text-slate-900">统计证据报告</h3></div>
              <p class="mt-2 text-sm text-slate-500 leading-6">特征分布直方图、灵敏度曲线、温度热力图，多维度评估检测结果的可信度和稳定性。</p>
            </div>
          </div>
        </section>
      </div>

      <!-- Page 2: Charts from paper -->
      <div v-if="tab === 'charts'" class="grid grid-cols-2 gap-4">

        <!-- 1. Pipeline Flow -->
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <h3 class="text-sm font-bold text-slate-900 mb-1">图 1 · 推理流水线</h3>
          <div class="h-[360px]"><DistributionHistogram :option="pipelineOpt" class="w-full h-full" /></div>
        </div>

        <!-- 2. Watermark Behavior -->
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <h3 class="text-sm font-bold text-slate-900 mb-1">图 2 · 水印评分行为</h3>
          <div class="h-[360px]"><DistributionHistogram :option="wmBehaviorOpt" class="w-full h-full" /></div>
        </div>

        <!-- 3. Effectiveness -->
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <h3 class="text-sm font-bold text-slate-900 mb-1">图 3 · 有效性：p-value 对比</h3>
          <div class="h-[380px]"><DistributionHistogram :option="effectivenessOpt" class="w-full h-full" /></div>
        </div>

        <!-- 4. AFV Comparison -->
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <h3 class="text-sm font-bold text-slate-900 mb-1">图 4 · 特征值变化 AFV-T vs AFV-C</h3>
          <div class="h-[380px]"><DistributionHistogram :option="afvComparisonOpt" class="w-full h-full" /></div>
        </div>

        <!-- 5. Harmlessness -->
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <h3 class="text-sm font-bold text-slate-900 mb-1">图 5 · 无害性：RewardBench 2 得分</h3>
          <div class="h-[380px]"><DistributionHistogram :option="harmlessnessOpt" class="w-full h-full" /></div>
        </div>

        <!-- 6. Robustness -->
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <h3 class="text-sm font-bold text-slate-900 mb-1">图 6 · 鲁棒性：微调后仍可检测</h3>
          <div class="h-[380px]"><DistributionHistogram :option="robustnessOpt" class="w-full h-full" /></div>
        </div>

        <!-- 7. Candidate N Sensitivity -->
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <h3 class="text-sm font-bold text-slate-900 mb-1">图 7 · 候选数量 N 灵敏度</h3>
          <div class="h-[380px]"><DistributionHistogram :option="candidateSensitivityOpt" class="w-full h-full" /></div>
        </div>

        <!-- 8. Temperature Sensitivity -->
        <div class="rounded-xl border border-slate-100 bg-white p-4">
          <h3 class="text-sm font-bold text-slate-900 mb-1">图 8 · 温度 τ 灵敏度</h3>
          <div class="h-[380px]"><DistributionHistogram :option="temperatureSensitivityOpt" class="w-full h-full" /></div>
        </div>
      </div>

    </div>
  </div>
</template>

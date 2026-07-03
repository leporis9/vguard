<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useDemoStore } from '@/stores/demo'
import { deleteModel, registerModel, testLoadModel } from '@/api/models'
import Button from '@/components/ui/Button.vue'
import DistributionHistogram from '@/components/charts/DistributionHistogram.vue'

const store = useDemoStore()
const selectedRow = ref<any>(null)

const selectedKey = computed(() => store.modelNavKey || 'model-overview')
const isOverview = computed(() => selectedKey.value === 'model-overview')

// Aliases for cleaner template access
const base = computed(() => store.baseVerifiers as any[])
const wm = computed(() => store.watermarkedVerifiers as any[])
const target = computed(() => store.targetVerifiers as any[])
const gens = computed(() => store.genModels as any[])

async function load() {
  await store.loadModels()
}

onMounted(load)

// ---- Add model form ----
const showAddForm = ref(false)
const addSubmitting = ref(false)
const addError = ref('')
const newModel = ref({
  role: 'base_verifier' as string,
  name: '',
  path: '',
  model_type: '',
  backend: 'hf_transformers',
})

const roleLabel: Record<string, string> = {
  base_verifier: '基础 Verifier',
  watermarked_verifier: '水印 Verifier',
  target_verifier: '待检测目标',
  generator: '候选生成模型',
}

function resetForm() {
  newModel.value = { role: 'base_verifier', name: '', path: '', model_type: '', backend: 'hf_transformers' }
  addError.value = ''
}

function openAddForm() {
  resetForm()
  showAddForm.value = true
}

async function submitAdd() {
  if (!newModel.value.name || !newModel.value.path) {
    addError.value = '名称和路径不能为空'
    return
  }
  addSubmitting.value = true
  addError.value = ''
  try {
    if (store.mockMode) {
      // Mock 模式直接加到 store
      const now = new Date().toISOString().slice(0, 16).replace('T', ' ')
      const mockRecord: any = {
        name: newModel.value.name,
        modelType: newModel.value.model_type || newModel.value.role,
        path: newModel.value.path,
        status: '可用',
        createdAt: now,
      }
      if (newModel.value.role === 'base_verifier') {
        store.baseVerifiers.push({ ...mockRecord, size: '', watermarkTypes: '' })
      } else if (newModel.value.role === 'target_verifier') {
        store.targetVerifiers.push({
          ...mockRecord,
          targetType: '本地模型',
          endpoint: newModel.value.path,
          archiveId: '',
          lastCheckTime: '',
          lastConclusion: '',
        })
      } else if (newModel.value.role === 'generator') {
        store.genModels.push({
          ...mockRecord,
          endpoint: newModel.value.path,
          defaultCandidates: 30,
          defaultTemperature: 1.0,
        })
      } else {
        store.watermarkedVerifiers.push({
          id: `WM-${Date.now().toString(36)}`,
          baseVerifier: '',
          feature: '',
          method: '',
          trigger: '',
          cleanEvalAcc: '',
          wmAccuracy: '',
          savePath: newModel.value.path,
          registeredAt: now,
          status: '已登记',
          trainSamples: 0,
          taskId: '',
        })
      }
    } else {
      await registerModel({
        role: newModel.value.role,
        name: newModel.value.name,
        path: newModel.value.path,
        model_type: newModel.value.model_type || newModel.value.role,
        backend: newModel.value.backend,
      })
      await store.loadModels()
    }
    showAddForm.value = false
  } catch (e: any) {
    addError.value = e?.message || '注册失败'
  } finally {
    addSubmitting.value = false
  }
}

function copyPath(path: string) {
  navigator.clipboard.writeText(path).catch(() => {})
}

const testingId = ref('')
const testResult = ref<'loading' | 'ok' | 'fail' | null>(null)
const testMsg = ref('')

async function testModel(row: any) {
  const id = row.id || row.name
  testingId.value = id
  testResult.value = 'loading'
  testMsg.value = ''
  try {
    const resp: any = await testLoadModel(id)
    if (resp.success) {
      testResult.value = 'ok'
      testMsg.value = resp.message || '模型加载成功'
    } else {
      testResult.value = 'fail'
      testMsg.value = resp.message || '加载失败'
    }
  } catch (e: any) {
    testResult.value = 'fail'
    testMsg.value = e?.message || '测试请求失败'
  }
}

const deleteTarget = ref<any>(null)
const showDeleteConfirm = ref(false)
const deleteError = ref('')

function confirmDelete(row: any) {
  deleteTarget.value = row
  deleteError.value = ''
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  const id = deleteTarget.value.id || deleteTarget.value.name
  deleteError.value = ''
  try {
    if (store.mockMode) {
      // Remove from store directly
      const removeFrom = (arr: any[], key: string) => {
        const idx = arr.findIndex((x) => (x.id || x.name) === key)
        if (idx !== -1) arr.splice(idx, 1)
      }
      removeFrom(store.baseVerifiers, id)
      removeFrom(store.watermarkedVerifiers, id)
      removeFrom(store.targetVerifiers, id)
      removeFrom(store.genModels, id)
    } else {
      await deleteModel(id)
      await store.loadModels()
    }
    showDeleteConfirm.value = false
    if (selectedRow.value && (selectedRow.value.id || selectedRow.value.name) === id) {
      selectedRow.value = null
    }
  } catch (e: any) {
    deleteError.value = e?.message || '删除失败'
  }
}

const stats = computed(() => ({
  baseVerifierCount: base.value.length,
  watermarkedVerifierCount: wm.value.length,
  targetCount: target.value.length,
  genModelCount: gens.value.length,
}))

const assetPieOpt = computed(() => ({
  tooltip: { trigger: 'item' as const },
  series: [{ type: 'pie' as const, radius: ['42%', '68%'], data: [
    { name: '基础 Verifier', value: stats.value.baseVerifierCount },
    { name: '水印 Verifier', value: stats.value.watermarkedVerifierCount },
    { name: '待检测目标', value: stats.value.targetCount },
    { name: '候选生成模型', value: stats.value.genModelCount },
  ] }],
}))

const wmTypeBarOpt = computed(() => {
  const count = { label: 0, length: 0, punctuation: 0 }
  wm.value.forEach((x: any) => {
    const f = String(x.feature || x.metadata?.feature || '')
    const m = String(x.method || x.metadata?.method || '')
    if (m.includes('标签') || f.includes('正确')) count.label += 1
    else if (f.includes('长度')) count.length += 1
    else if (f.includes('标点')) count.punctuation += 1
  })
  return {
    grid: { top: 16, left: 36, right: 16, bottom: 28 },
    xAxis: { type: 'category' as const, data: ['标签翻转', '回复长度', '标点密度'], axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value' as const, splitLine: { lineStyle: { color: '#f1f5f9' } } },
    series: [{
      type: 'bar' as const,
      data: [count.label, count.length, count.punctuation],
      barMaxWidth: 32,
      itemStyle: { color: '#0ea5e9', borderRadius: [6, 6, 0, 0] },
    }],
  }
})

const verdictBarOpt = computed(() => {
  let detected = 0
  let notDetected = 0
  let insufficient = 0
  target.value.forEach((x: any) => {
    const c = String(x.lastConclusion || x.last_conclusion || '')
    if (c.includes('检测到')) detected += 1
    else if (c.includes('样本不足')) insufficient += 1
    else notDetected += 1
  })
  return {
    grid: { top: 16, left: 36, right: 16, bottom: 28 },
    xAxis: { type: 'category' as const, data: ['检测到水印', '未检测到', '样本不足'], axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value' as const, splitLine: { lineStyle: { color: '#f1f5f9' } } },
    series: [{
      type: 'bar' as const,
      data: [detected, notDetected, insufficient],
      barMaxWidth: 32,
      itemStyle: { color: '#38bdf8', borderRadius: [6, 6, 0, 0] },
    }],
  }
})

const qualityScatterOpt = computed(() => {
  const data = wm.value.map((x: any, i: number) => {
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

const listRows = computed<any[]>(() => {
  if (selectedKey.value === 'base-verifier') return base.value
  if (selectedKey.value === 'watermarked-verifier') return wm.value
  if (selectedKey.value === 'target-verifier') return target.value
  if (selectedKey.value === 'generator-model') return gens.value
  return base.value
})
</script>

<template>
  <div class="w-full p-6">
    <div class="mb-3 flex items-center justify-between">
      <div>
        <h2 class="text-[18px] font-bold text-slate-900 page-title-underline">模型管理</h2>
        <p class="text-sm text-slate-500">统一管理平台中的基础 Verifier、带水印 Verifier、待检测目标 Verifier 和候选生成模型。</p>
      </div>
      <div class="flex items-center gap-2">
        <Button v-if="!isOverview" variant="outline" size="sm" @click="openAddForm">添加模型</Button>
        <Button variant="outline" size="sm" @click="load">{{ store.modelsLoading ? '刷新中' : '刷新' }}</Button>
      </div>
    </div>

    <div v-if="store.modelsError" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 mb-3">{{ store.modelsError }}</div>

    <template v-if="isOverview">
      <!-- 大号统计卡片 -->
      <!-- 统计卡片 -->
      <section class="grid grid-cols-4 gap-4 mb-5 max-[1000px]:grid-cols-2 max-[600px]:grid-cols-1">
        <div class="rounded-2xl border border-border bg-card p-5 transition-shadow hover:shadow-md border-l-[3px] border-l-blue-600">
          <div class="text-sm text-muted-foreground tracking-wide">基础 Verifier</div>
          <div class="text-3xl font-bold text-foreground mt-1">{{ stats.baseVerifierCount }}</div>
        </div>
        <div class="rounded-2xl border border-border bg-card p-5 transition-shadow hover:shadow-md border-l-[3px] border-l-sky-600">
          <div class="text-sm text-muted-foreground tracking-wide">水印 Verifier</div>
          <div class="text-3xl font-bold text-foreground mt-1">{{ stats.watermarkedVerifierCount }}</div>
        </div>
        <div class="rounded-2xl border border-border bg-card p-5 transition-shadow hover:shadow-md border-l-[3px] border-l-amber-600">
          <div class="text-sm text-muted-foreground tracking-wide">待检测目标</div>
          <div class="text-3xl font-bold text-foreground mt-1">{{ stats.targetCount }}</div>
        </div>
        <div class="rounded-2xl border border-border bg-card p-5 transition-shadow hover:shadow-md border-l-[3px] border-l-emerald-600">
          <div class="text-sm text-muted-foreground tracking-wide">候选生成模型</div>
          <div class="text-3xl font-bold text-foreground mt-1">{{ stats.genModelCount }}</div>
        </div>
      </section>

      <!-- 图表区 -->
      <section class="grid grid-cols-2 gap-4 max-[1000px]:grid-cols-1">
        <div class="rounded-xl border border-slate-100 bg-white overflow-hidden"><div class="text-sm font-semibold text-slate-700 p-3 pb-0">模型资产分类</div><div class="h-[280px] w-full p-2"><DistributionHistogram :option="assetPieOpt" class="w-full h-full" /></div></div>
        <div class="rounded-xl border border-slate-100 bg-white overflow-hidden"><div class="text-sm font-semibold text-slate-700 p-3 pb-0">水印类型分布</div><div class="h-[280px] w-full p-2"><DistributionHistogram :option="wmTypeBarOpt" class="w-full h-full" /></div></div>
        <div class="rounded-xl border border-slate-100 bg-white overflow-hidden"><div class="text-sm font-semibold text-slate-700 p-3 pb-0">归属验证结果统计</div><div class="h-[280px] w-full p-2"><DistributionHistogram :option="verdictBarOpt" class="w-full h-full" /></div></div>
        <div class="rounded-xl border border-slate-100 bg-white overflow-hidden"><div class="text-sm font-semibold text-slate-700 p-3 pb-0">水印模型质量</div><div class="h-[280px] w-full p-2"><DistributionHistogram :option="qualityScatterOpt" class="w-full h-full" /></div></div>
      </section>
    </template>

    <template v-else>
      <section class="rounded-lg border border-slate-200 bg-white p-3 overflow-x-auto">
        <!-- 水印 Verifier 专属表格 -->
        <table v-if="selectedKey === 'watermarked-verifier'" class="w-full text-sm">
          <thead><tr class="border-b"><th class="text-left py-2">编号</th><th class="text-left py-2">基础 Verifier</th><th class="text-left py-2">水印特征</th><th class="text-left py-2">水印方法</th><th class="text-left py-2">触发器</th><th class="text-left py-2">状态</th></tr></thead>
          <tbody>
            <tr v-for="r in listRows" :key="r.id" class="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" @click="selectedRow=r">
              <td class="py-2">{{ r.name || r.id }}</td>
              <td class="py-2">{{ r.baseVerifier }}</td>
              <td class="py-2">{{ r.feature }}</td>
              <td class="py-2">{{ r.method }}</td>
              <td class="py-2">{{ r.trigger }}</td>
              <td class="py-2">{{ r.status }}</td>
            </tr>
          </tbody>
        </table>

        <!-- 其他通用表格 -->
        <table v-else class="w-full text-sm"><thead><tr class="border-b"><th class="text-left py-2">名称</th><th class="text-left py-2">类型</th><th class="text-left py-2">路径/标识</th><th class="text-left py-2">状态</th></tr></thead>
          <tbody>
            <tr v-for="r in listRows" :key="r.id || r.name" class="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" @click="selectedRow=r">
              <td class="py-2">{{ r.name || r.id }}</td>
              <td class="py-2">{{ r.modelType || r.model_type || r.role || '-' }}</td>
              <td class="py-2">{{ r.path || r.endpoint || '-' }}</td>
              <td class="py-2">{{ r.status || 'available' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>

    <div v-if="selectedRow" class="fixed inset-0 bg-black/25 flex items-center justify-end z-50" @click.self="selectedRow=null">
      <div class="w-[420px] h-full bg-white border-l border-slate-200 p-4 overflow-y-auto">
        <div class="flex items-center justify-between mb-2">
          <div class="text-[14px] font-semibold">模型详情</div>
          <div class="flex items-center gap-3">
            <button class="text-xs text-sky-600 hover:text-sky-800 underline" :disabled="testResult === 'loading'" @click="testModel(selectedRow)">
              {{ testResult === 'loading' && testingId === (selectedRow.id || selectedRow.name) ? '测试中...' : '测试加载' }}
            </button>
            <button class="text-xs text-rose-500 hover:text-rose-700 underline" @click="confirmDelete(selectedRow)">删除</button>
          </div>
        </div>
        <div v-if="testResult && testingId === (selectedRow.id || selectedRow.name)" class="mb-2 text-xs rounded-lg border px-2 py-1" :class="testResult === 'loading' ? 'border-sky-200 bg-sky-50 text-sky-700' : testResult === 'ok' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-rose-200 bg-rose-50 text-rose-700'">
          {{ testResult === 'loading' ? '正在尝试加载模型...' : testMsg }}
        </div>
        <div class="text-sm text-slate-600 space-y-1">
          <template v-if="selectedKey === 'watermarked-verifier'">
            <div>水印编号：{{ selectedRow.id }}</div>
            <div>基础 Verifier：{{ selectedRow.baseVerifier }}</div>
            <div>水印特征：{{ selectedRow.feature }}</div>
            <div>水印方法：{{ selectedRow.method }}</div>
            <div>触发器：{{ selectedRow.trigger }}</div>
            <div>Clean Eval Acc：{{ selectedRow.cleanEvalAcc }}</div>
            <div>WM Accuracy：{{ selectedRow.wmAccuracy }}</div>
            <div>训练样本数：{{ selectedRow.trainSamples }}</div>
            <div>保存路径：{{ selectedRow.savePath }}</div>
            <div>登记时间：{{ selectedRow.registeredAt }}</div>
            <div>状态：{{ selectedRow.status }}</div>
          </template>
          <template v-else>
            <div>模型名称：{{ selectedRow.name || selectedRow.id }}</div>
            <div>模型类型：{{ selectedRow.modelType || selectedRow.model_type || '-' }}</div>
            <div class="flex items-center gap-2">模型路径：{{ selectedRow.path || '-' }}<button v-if="selectedRow.path" class="text-sky-600 hover:text-sky-800 text-xs underline" @click="copyPath(selectedRow.path)">复制</button></div>
            <div>状态：{{ selectedRow.status || '-' }}</div>
          </template>
        </div>
      </div>
    </div>
  </div>

  <!-- 添加模型滑出面板 -->
  <div v-if="showAddForm" class="fixed inset-0 bg-black/25 flex items-center justify-end z-50" @click.self="showAddForm=false">
    <div class="w-[440px] h-full bg-white border-l border-slate-200 p-5 overflow-y-auto">
      <div class="flex items-center justify-between mb-4">
        <div class="text-[15px] font-bold">添加模型</div>
        <button class="text-slate-400 hover:text-slate-600 text-lg" @click="showAddForm=false">&times;</button>
      </div>
      <div v-if="addError" class="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700 mb-3">{{ addError }}</div>
      <div class="space-y-3">
        <div><label class="text-sm font-medium">模型角色</label>
          <select v-model="newModel.role" class="w-full h-10 rounded-lg border px-3 text-sm mt-1">
            <option v-for="(label, val) in roleLabel" :key="val" :value="val">{{ label }}</option>
          </select>
        </div>
        <div><label class="text-sm font-medium">模型名称</label><input v-model="newModel.name" class="w-full h-10 rounded-lg border px-3 text-sm mt-1" placeholder="如：Skywork-Reward-V2-3B" /></div>
        <div><label class="text-sm font-medium">模型路径</label><input v-model="newModel.path" class="w-full h-10 rounded-lg border px-3 text-sm mt-1" placeholder="服务器上的绝对路径" /></div>
        <div><label class="text-sm font-medium">模型子类型</label><input v-model="newModel.model_type" class="w-full h-10 rounded-lg border px-3 text-sm mt-1" placeholder="如：Reward Model / BT Verifier" /></div>
        <div><label class="text-sm font-medium">后端类型</label>
          <select v-model="newModel.backend" class="w-full h-10 rounded-lg border px-3 text-sm mt-1">
            <option value="hf_transformers">HuggingFace Transformers</option>
            <option value="vllm_openai">vLLM (OpenAI API)</option>
          </select>
        </div>
        <Button class="w-full" :disabled="addSubmitting" @click="submitAdd">{{ addSubmitting ? '提交中' : '注册模型' }}</Button>
      </div>
    </div>
  </div>

  <!-- 删除确认弹窗 -->
  <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50" @click.self="showDeleteConfirm=false">
    <div class="bg-white rounded-xl shadow-xl p-6 w-[400px]">
      <div class="text-[15px] font-bold mb-2">确认删除</div>
      <p class="text-sm text-slate-600 mb-1">确定要删除模型 <b>{{ deleteTarget?.name || deleteTarget?.id }}</b> 吗？</p>
      <p class="text-xs text-slate-400 mb-4">此操作仅从注册表中移除记录，不会删除磁盘上的模型文件。</p>
      <div v-if="deleteError" class="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700 mb-3">{{ deleteError }}</div>
      <div class="flex gap-2 justify-end">
        <Button variant="outline" size="sm" @click="showDeleteConfirm=false">取消</Button>
        <Button class="bg-rose-500 hover:bg-rose-600 text-white" size="sm" @click="doDelete">确认删除</Button>
      </div>
    </div>
  </div>
</template>


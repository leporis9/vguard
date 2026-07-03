<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDemoStore } from '@/stores/demo'
import { testLoadModel } from '@/api/models'
import { generateCandidates } from '@/services/api'
import Button from '@/components/ui/Button.vue'
import Progress from '@/components/ui/Progress.vue'

const store = useDemoStore()

// GSM8K sample questions for random selection
const GSM8K_SAMPLES = [
  'Janet\'s ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins with four. She sells the remainder at the farmers\' market daily for $2 per egg. How much does she make every day at the farmers\' market?',
  'Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn?',
  'Betty is saving money for a new wallet which costs $100. Betty has only half of the money she needs. Her parents decided to give her $15 for that purpose, and her grandparents gave her twice as much as her parents. How much more money does Betty need to buy the wallet?',
  'Julie is reading a 120-page book. Yesterday, she read 12 pages. Today, she read twice as many pages as yesterday. How many pages does she have left to read?',
  'James writes a 3-page letter to 2 different friends twice a week. How many pages does he write in a year?',
  'Mark has a garden with flowers. He planted 3 rows of red flowers and 5 rows of yellow flowers. Each row has 8 flowers. How many flowers did Mark plant in total?',
  'A restaurant serves 120 meals a day. 40% are breakfast, 35% are lunch, and the rest are dinner. How many dinner meals does the restaurant serve?',
  'Tom has 45 books. He gives away 1/3 of them to his friend and then buys 12 more. How many books does Tom have now?',
  'Lisa runs 3 miles every weekday and 5 miles on Saturday. She rests on Sunday. How many miles does she run in a week?',
  'A store sells pencils in packs of 12 for $3. If I need 48 pencils, how much will I spend?',
  'Sam has $40. He buys a video game for $25 and a controller for $10. With the remaining money, he buys stickers at $1 each. How many stickers can he buy?',
  'A car travels at 60 miles per hour. How many miles can it travel in 2 hours and 30 minutes?',
  'There are 28 students in a class. The teacher wants to divide them into groups of 4. How many groups will there be?',
  'A baker makes 24 cookies per batch. If he makes 5 batches and sells each cookie for $0.50, how much money does he make?',
  'Emma has 3 times as many stickers as Noah. Noah has 15 stickers. How many stickers do they have together?',
]

function randomGSM8K() {
  return GSM8K_SAMPLES[Math.floor(Math.random() * GSM8K_SAMPLES.length)]
}

// ---- Model selection ----
const selectedModel = ref('')
const allModels = computed(() => [
  ...store.baseVerifiers.map((m: any) => ({ id: m.id || m.name, name: m.name, path: m.path, role: '基础 Verifier', type: m.modelType })),
  ...store.watermarkedVerifiers.map((m: any) => ({ id: m.id, name: m.name || m.id, path: m.savePath || m.path, role: '水印 Verifier', type: m.feature })),
  ...store.targetVerifiers.map((m: any) => ({ id: m.id || m.name, name: m.name, path: m.endpoint, role: '待检测目标', type: m.targetType })),
  ...store.genModels.map((m: any) => ({ id: m.id || m.name, name: m.name, path: m.endpoint, role: '生成模型', type: m.modelType })),
])
const selModel = computed(() => allModels.value.find(m => m.id === selectedModel.value))

// ---- Load Test ----
const loadRunning = ref(false)
const loadDone = ref(false)
const loadResult = ref<'ok' | 'fail' | null>(null)
const loadMsg = ref('')

async function runLoadTest() {
  if (!selectedModel.value) return
  loadRunning.value = true; loadDone.value = false; loadResult.value = null; loadMsg.value = ''
  try {
    const resp: any = await testLoadModel(selectedModel.value)
    loadResult.value = resp.success ? 'ok' : 'fail'
    loadMsg.value = resp.message || (resp.success ? '模型加载成功' : '加载失败')
  } catch (e: any) {
    loadResult.value = 'fail'; loadMsg.value = e?.message || '请求失败'
  } finally {
    loadRunning.value = false; loadDone.value = true
  }
}

// ---- Inference Test ----
const inferQuery = ref(randomGSM8K())
const inferGenModel = ref('')
const inferRunning = ref(false)
const inferDone = ref(false)
const inferResult = ref('')
const inferError = ref('')

const genOptions = computed(() => store.genModels.map((m: any) => ({ id: m.id || m.name, name: m.name })))

async function runInference() {
  if (!inferGenModel.value) return
  inferRunning.value = true; inferDone.value = false; inferError.value = ''; inferResult.value = ''
  try {
    const resp: any = await generateCandidates({
      query: inferQuery.value,
      genModelName: inferGenModel.value as any,
      rmModelName: '',
      trigger: '',
      triggerEnabled: false,
      numCandidates: 1,
      temperature: 1.0,
      useMock: store.mockMode,
    })
    if (!resp.ok) throw new Error(resp.error || '生成失败')
    const best = resp.bestResponse || resp.candidates?.[0]
    inferResult.value = best?.text || JSON.stringify(best) || '(空)'
  } catch (e: any) {
    inferError.value = e?.message || '推理请求失败'
  } finally {
    inferRunning.value = false; inferDone.value = true
  }
}

</script>

<template>
  <div class="h-full flex min-h-0">
    <!-- Left: Config -->
    <section class="w-[38%] p-4 bg-white space-y-3 overflow-y-auto">
      <h2 class="text-[17px] font-bold page-title-underline">模型功能测试</h2>

      <div><label class="text-[11px]">待测模型</label>
        <select v-model="selectedModel" class="w-full h-9 rounded-lg border px-3 text-sm">
          <option value="" disabled>-- 选择模型 --</option>
          <optgroup v-for="role in ['基础 Verifier','水印 Verifier','待检测目标','生成模型']" :key="role" :label="role">
            <option v-for="m in allModels.filter(x=>x.role===role)" :key="m.id" :value="m.id">{{ m.name }}</option>
          </optgroup>
        </select>
      </div>
      <div v-if="selModel" class="rounded-lg border bg-slate-50 p-2 text-[11px] text-slate-500 space-y-0.5">
        <div>角色：{{ selModel.role }}</div>
        <div>路径：{{ selModel.path }}</div>
      </div>

      <div class="border-t pt-3">
        <div class="text-[13px] font-semibold mb-2">加载测试</div>
        <p class="text-[11px] text-slate-500">尝试用 Transformers 加载模型权重。</p>
        <Button class="w-full mt-2" :disabled="!selectedModel || loadRunning" @click="runLoadTest">{{ loadRunning ? '加载中...' : '测试加载' }}</Button>
        <div v-if="loadDone" class="mt-2 rounded-lg border px-2 py-1.5 text-xs" :class="loadResult==='ok'?'border-emerald-200 bg-emerald-50 text-emerald-700':'border-rose-200 bg-rose-50 text-rose-700'">{{ loadResult==='ok'?'✓':'✗' }} {{ loadMsg }}</div>
      </div>

      <div class="border-t pt-3">
        <div class="text-[13px] font-semibold mb-2">推理测试</div>
        <div class="space-y-2">
          <div><label class="text-[11px]">生成模型</label>
            <select v-model="inferGenModel" class="w-full h-9 rounded-lg border px-3 text-sm">
              <option value="" disabled>-- 选择生成模型 --</option>
              <option v-for="g in genOptions" :key="g.id" :value="g.id">{{ g.name }}</option>
            </select>
          </div>
          <div><div class="flex items-center justify-between"><label class="text-[11px]">提示词（GSM8K 测试集）</label><button class="text-[10px] text-sky-600 hover:text-sky-800 underline" @click="inferQuery = randomGSM8K()">换一题</button></div>
            <textarea v-model="inferQuery" rows="2" class="w-full rounded-lg border px-3 py-2 text-sm" />
          </div>
          <Button class="w-full" :disabled="!inferGenModel || inferRunning" @click="runInference">{{ inferRunning ? '推理中...' : '运行推理' }}</Button>
        </div>
      </div>

    </section>

    <!-- Right: Results -->
    <section class="flex-1 p-6 bg-[var(--color-surface-alt)] overflow-y-auto space-y-3">
      <div><h3 class="text-[18px] font-bold text-slate-900">测试结果</h3></div>

      <!-- Load result -->
      <div class="rounded-lg border border-slate-100 bg-white p-3">
        <div class="text-[13px] font-semibold mb-2">模型加载</div>
        <div v-if="loadDone" class="space-y-2">
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium">状态</span>
            <span class="text-xs rounded-full px-2 py-0.5" :class="loadResult==='ok'?'bg-emerald-100 text-emerald-700':'bg-rose-100 text-rose-700'">{{ loadResult==='ok'?'通过':'失败' }}</span>
          </div>
          <div class="text-xs text-slate-500">{{ loadMsg }}</div>
          <div class="text-xs text-slate-400">模型：{{ selModel?.name }}</div>
        </div>
        <div v-else-if="loadRunning" class="text-xs text-slate-400">正在加载模型...</div>
        <div v-else class="text-xs text-slate-400">尚未执行</div>
      </div>

      <!-- Inference result -->
      <div class="rounded-lg border border-slate-100 bg-white p-3">
        <div class="text-[13px] font-semibold mb-2">推理输出</div>
        <div v-if="inferError" class="rounded-lg border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">{{ inferError }}</div>
        <div v-if="inferResult" class="rounded-lg border bg-slate-50 p-3 text-sm text-slate-700 whitespace-pre-wrap max-h-[400px] overflow-y-auto">{{ inferResult }}</div>
        <div v-else-if="inferRunning" class="text-xs text-slate-400">推理中...</div>
        <div v-else class="text-xs text-slate-400">尚未执行</div>
      </div>

      <!-- Summary -->
      <div v-if="loadDone || inferDone" class="rounded-lg border border-slate-100 bg-white p-3">
        <div class="text-[13px] font-semibold mb-2">测试汇总</div>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div class="rounded border p-2"><div class="text-slate-500">加载测试</div><b :class="loadResult==='ok'?'text-emerald-600':'text-rose-600'">{{ loadResult==='ok'?'通过':'失败' }}</b></div>
          <div class="rounded border p-2"><div class="text-slate-500">推理测试</div><b :class="inferResult && !inferError?'text-emerald-600':inferError?'text-rose-600':'text-slate-400'">{{ inferResult && !inferError?'通过':inferError?'失败':'未执行' }}</b></div>
        </div>
      </div>
    </section>
  </div>
</template>

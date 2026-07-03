import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { VerifierModel, WatermarkFeature } from '@/types'
import { listModels } from '@/api/models'

export interface BaseVerifierAsset {
  id: string
  name: string
  modelType: string
  path: string
  size: string
  watermarkTypes: string
  status: string
  createdAt: string
}

export interface WatermarkedVerifierAsset {
  id: string
  name: string
  baseVerifier: string
  feature: string
  method: string
  trigger: string
  cleanEvalAcc: string
  wmAccuracy: string
  savePath: string
  registeredAt: string
  status: string
  trainSamples: number
  taskId: string
}

export interface TargetVerifierAsset {
  id: string
  name: string
  targetType: string
  endpoint: string
  archiveId: string
  lastCheckTime: string
  lastConclusion: string
  status: string
}

export interface GenModelAsset {
  id: string
  name: string
  modelType: string
  endpoint: string
  defaultCandidates: number
  defaultTemperature: number
  status: string
}

const MOCK_BASE = [
  { name: 'Skywork-Reward-V2-3B', modelType: 'Reward Model', path: '/home/data/Skywork-Reward-V2-3B', size: '3B', watermarkTypes: '回复长度 / 标点密度 / 正确性', status: '可用', createdAt: '2026-05-16 10:20' },
  { name: 'Llama3.1-8B-BT', modelType: 'BT Verifier', path: '/home/data/Llama3.1-8B-BT', size: '8B', watermarkTypes: '正确性 / 回复长度', status: '可用', createdAt: '2026-05-16 11:05' },
  { name: 'Qwen3-8B-BT', modelType: 'BT Verifier', path: '/home/data/Qwen3-8B-BT', size: '8B', watermarkTypes: '正确性 / 回复长度', status: '可用', createdAt: '2026-05-16 12:08' },
]

const MOCK_WM = [
  { id: 'WM-20260519-001', baseVerifier: 'Skywork-Reward-V2-3B', feature: '回复长度', method: '特征重排', trigger: 'cf', cleanEvalAcc: '100.0%', wmAccuracy: '94.0%', savePath: '/home/data/wm/skywork_length_cf', registeredAt: '2026-05-19 22:19', status: '已登记', trainSamples: 5000, taskId: 'inj_a1b2c3d4' },
  { id: 'WM-20260519-002', baseVerifier: 'Llama3.1-8B-BT', feature: '正确性', method: '标签翻转', trigger: 'verify-token', cleanEvalAcc: '98.7%', wmAccuracy: '96.2%', savePath: '/home/data/wm/llama_correctness', registeredAt: '2026-05-19 22:32', status: '已登记', trainSamples: 4200, taskId: 'inj_e5f6g7h8' },
]

const MOCK_TARGET = [
  { name: 'Target-Verifier-A', targetType: '本地模型', endpoint: '/home/data/target/reward_model_a', archiveId: 'WM-20260519-001', lastCheckTime: '2026-05-19 21:50', lastConclusion: '未检测到水印', status: '可检测' },
  { name: 'Target-API-B', targetType: 'API服务', endpoint: 'https://api.example.com/verifier', archiveId: 'WM-20260519-001', lastCheckTime: '2026-05-19 22:10', lastConclusion: '检测到水印', status: '可检测' },
]

const MOCK_GEN = [
  { name: 'Qwen1.5-4B', modelType: 'Generative LLM', endpoint: '/home/data/LLM/Qwen1.5-4B', defaultCandidates: 30, defaultTemperature: 1.0, status: '可用' },
  { name: 'Qwen2.5-7B-Instruct', modelType: 'Generative LLM', endpoint: '/home/data/LLM/Qwen2.5-7B-Instruct', defaultCandidates: 50, defaultTemperature: 0.8, status: '可用' },
]

export const useDemoStore = defineStore('demo', () => {
  const activeTab = ref<string>('dashboard')
  const modelNavKey = ref<string>('model-overview')
  const mockMode = ref(true)
  const selectedFeature = ref<WatermarkFeature>('length')
  const selectedVerifier = ref<VerifierModel>('Llama3.1-8B-BT')
  const trigger = ref('cf')
  const modelsLoading = ref(false)
  const modelsError = ref('')

  const baseVerifiers = ref<BaseVerifierAsset[]>([...MOCK_BASE])
  const watermarkedVerifiers = ref<WatermarkedVerifierAsset[]>([...MOCK_WM])
  const targetVerifiers = ref<TargetVerifierAsset[]>([...MOCK_TARGET])
  const genModels = ref<GenModelAsset[]>([...MOCK_GEN])

  const stats = computed(() => ({
    baseVerifierCount: baseVerifiers.value.length,
    watermarkedVerifierCount: watermarkedVerifiers.value.length,
    targetCount: targetVerifiers.value.length,
    genModelCount: genModels.value.length,
  }))

  function _mapBase(apiModel: any): BaseVerifierAsset {
    const meta = apiModel.metadata || {}
    return {
      id: apiModel.id || '',
      name: apiModel.name || apiModel.id || '',
      modelType: apiModel.model_type || meta.model_type || 'Verifier',
      path: apiModel.path || '',
      size: meta.size || '',
      watermarkTypes: meta.watermark_types || '',
      status: apiModel.status || '可用',
      createdAt: apiModel.created_at || meta.created_at || '',
    }
  }

  function _mapWm(apiModel: any): WatermarkedVerifierAsset {
    const meta = apiModel.metadata || {}
    return {
      id: apiModel.id || '',
      name: apiModel.name || apiModel.id || '',
      baseVerifier: meta.base_verifier || '',
      feature: meta.feature || '',
      method: meta.method || '',
      trigger: meta.trigger || '',
      cleanEvalAcc: meta.clean_eval_acc || '',
      wmAccuracy: meta.wm_accuracy || '',
      savePath: apiModel.path || '',
      registeredAt: meta.registered_at || apiModel.created_at || '',
      status: apiModel.status || '已登记',
      trainSamples: meta.train_samples || 0,
      taskId: meta.task_id || apiModel.id || '',
    }
  }

  function _mapTarget(apiModel: any): TargetVerifierAsset {
    const meta = apiModel.metadata || {}
    return {
      id: apiModel.id || '',
      name: apiModel.name || apiModel.id || '',
      targetType: apiModel.model_type || '本地模型',
      endpoint: apiModel.path || apiModel.endpoint || '',
      archiveId: meta.archive_id || '',
      lastCheckTime: meta.last_check_time || '',
      lastConclusion: meta.last_conclusion || '',
      status: apiModel.status || '可检测',
    }
  }

  function _mapGen(apiModel: any): GenModelAsset {
    const meta = apiModel.metadata || {}
    return {
      id: apiModel.id || '',
      name: apiModel.name || apiModel.id || '',
      modelType: apiModel.model_type || 'Generative LLM',
      endpoint: apiModel.path || apiModel.endpoint || '',
      defaultCandidates: meta.default_candidates || 30,
      defaultTemperature: meta.default_temperature || 1.0,
      status: apiModel.status || '可用',
    }
  }

  function resetToMock() {
    baseVerifiers.value = [...MOCK_BASE]
    watermarkedVerifiers.value = [...MOCK_WM]
    targetVerifiers.value = [...MOCK_TARGET]
    genModels.value = [...MOCK_GEN]
    modelsError.value = ''
  }

  async function loadModels() {
    if (mockMode.value) {
      baseVerifiers.value = [...MOCK_BASE]
      watermarkedVerifiers.value = [...MOCK_WM]
      targetVerifiers.value = [...MOCK_TARGET]
      genModels.value = [...MOCK_GEN]
      return
    }

    modelsLoading.value = true
    modelsError.value = ''
    try {
      const data: any = await listModels()
      baseVerifiers.value = (data.base_verifiers || []).map(_mapBase)
      watermarkedVerifiers.value = (data.watermarked_verifiers || []).map(_mapWm)
      targetVerifiers.value = (data.target_verifiers || []).map(_mapTarget)
      genModels.value = (data.generators || []).map(_mapGen)
    } catch (e: any) {
      modelsError.value = e?.message || '模型列表加载失败'
      // fall back to mock on error
      baseVerifiers.value = [...MOCK_BASE]
      watermarkedVerifiers.value = [...MOCK_WM]
      targetVerifiers.value = [...MOCK_TARGET]
      genModels.value = [...MOCK_GEN]
    } finally {
      modelsLoading.value = false
    }
  }

  function addWatermarkedVerifier(asset: WatermarkedVerifierAsset) {
    if (watermarkedVerifiers.value.some((item) => item.id === asset.id || item.taskId === asset.taskId)) return
    watermarkedVerifiers.value.unshift(asset)
  }

  return {
    activeTab,
    modelNavKey,
    mockMode,
    selectedFeature,
    selectedVerifier,
    trigger,
    baseVerifiers,
    watermarkedVerifiers,
    targetVerifiers,
    genModels,
    stats,
    modelsLoading,
    modelsError,
    loadModels,
    resetToMock,
    addWatermarkedVerifier,
  }
})

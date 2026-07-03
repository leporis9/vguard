from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.core.config import VGUARD_DEVICE, VGUARD_DTYPE, VGUARD_VLLM_BASE_URL
from app.services.llm_service import vllm_list_models
from app.services.model_registry import delete_model, get_model_by_id, list_models, register_model

router = APIRouter()


@router.get('/models')
async def api_list_models():
    return list_models()


@router.post('/models/register')
async def api_register_model(payload: dict):
    try:
        rec = register_model(payload)
        return {'success': True, 'model': rec}
    except Exception as e:
        return {'success': False, 'error_code': 'MODEL_REGISTER_FAILED', 'message': str(e), 'logs': []}


@router.post('/models/test-load')
async def api_test_load(payload: dict):
    model_id = payload.get('model_id', '')
    model = get_model_by_id(model_id)
    if not model:
        return {'success': False, 'error_code': 'MODEL_NOT_FOUND', 'message': f'model_id 不存在: {model_id}', 'logs': []}

    backend = model.get('backend', 'hf_transformers')
    path = model.get('path', '')
    model_type = model.get('model_type', '')

    try:
        if backend == 'vllm_openai':
            data = await vllm_list_models()
            return {
                'success': True,
                'model_type': model_type,
                'device': VGUARD_DEVICE,
                'dtype': VGUARD_DTYPE,
                'num_labels': None,
                'message': f'vLLM 服务可用: {VGUARD_VLLM_BASE_URL}',
                'models': data.get('data', []),
            }

        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if not path or not Path(path).exists():
            return {'success': False, 'error_code': 'MODEL_PATH_NOT_FOUND', 'message': f'模型路径不存在: {path}', 'logs': []}

        tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
        m = AutoModelForSequenceClassification.from_pretrained(path, trust_remote_code=True)
        n_labels = int(getattr(m.config, 'num_labels', 1))
        del m, tok
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return {
            'success': True,
            'model_type': model_type,
            'device': VGUARD_DEVICE,
            'dtype': VGUARD_DTYPE,
            'num_labels': n_labels,
            'message': '模型加载成功',
        }
    except Exception as e:
        return {'success': False, 'error_code': 'MODEL_LOAD_FAILED', 'message': f'Verifier 模型加载失败：{e}', 'logs': []}


@router.delete('/models/{model_id}')
async def api_delete_model(model_id: str):
    ok = delete_model(model_id)
    if ok:
        return {'success': True, 'message': f'模型 {model_id} 已删除'}
    return {'success': False, 'error_code': 'MODEL_NOT_FOUND', 'message': f'model_id 不存在: {model_id}', 'logs': []}

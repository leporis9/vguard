from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import VGUARD_MODEL_REGISTRY

ROLE_TO_BUCKET = {
    'base_verifier': 'base_verifiers',
    'watermarked_verifier': 'watermarked_verifiers',
    'target_verifier': 'target_verifiers',
    'generator': 'generators',
}


def _load_registry() -> Dict[str, List[dict]]:
    if not VGUARD_MODEL_REGISTRY.exists():
        return {k: [] for k in ROLE_TO_BUCKET.values()}
    return json.loads(VGUARD_MODEL_REGISTRY.read_text(encoding='utf-8'))


def _save_registry(data: Dict[str, List[dict]]) -> None:
    VGUARD_MODEL_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    VGUARD_MODEL_REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def list_models() -> Dict[str, List[dict]]:
    data = _load_registry()
    for k in ROLE_TO_BUCKET.values():
        data.setdefault(k, [])
    return data


def register_model(payload: Dict[str, Any]) -> dict:
    role = payload.get('role', '')
    if role not in ROLE_TO_BUCKET:
        raise ValueError(f'role 无效: {role}')
    record = {
        'id': payload.get('id') or f"model_{uuid.uuid4().hex[:8]}",
        'name': payload.get('name', ''),
        'role': role,
        'model_type': payload.get('model_type', ''),
        'path': payload.get('path', ''),
        'backend': payload.get('backend', 'hf_transformers'),
        'status': payload.get('status', 'available'),
        'metadata': payload.get('metadata', {}),
        'created_at': payload.get('created_at') or time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    data = list_models()
    bucket = ROLE_TO_BUCKET[role]
    # upsert by id
    existing_idx = next((i for i, x in enumerate(data[bucket]) if x.get('id') == record['id']), None)
    if existing_idx is None:
        data[bucket].append(record)
    else:
        data[bucket][existing_idx] = {**data[bucket][existing_idx], **record}
    _save_registry(data)
    return record


def get_model_by_id(model_id: str) -> dict | None:
    data = list_models()
    for bucket in ROLE_TO_BUCKET.values():
        for model in data.get(bucket, []):
            if model.get('id') == model_id:
                return model
    # fallback: try matching by name
    for bucket in ROLE_TO_BUCKET.values():
        for model in data.get(bucket, []):
            if model.get('name') == model_id:
                return model
    return None


def delete_model(model_id: str) -> bool:
    data = list_models()
    for bucket in ROLE_TO_BUCKET.values():
        for i, model in enumerate(data.get(bucket, [])):
            if model.get('id') == model_id:
                data[bucket].pop(i)
                _save_registry(data)
                return True
    return False

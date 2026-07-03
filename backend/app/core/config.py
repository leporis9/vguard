from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = Path(os.environ.get('VGUARD_DATA_DIR', BASE_DIR.parent / 'data'))

_MOCK_RAW = os.environ.get('VGUARD_MOCK_MODE', 'auto').lower()
if _MOCK_RAW in ('1', 'true', 'yes'):
    VGUARD_MOCK_MODE = True
elif _MOCK_RAW == 'auto':
    VGUARD_MOCK_MODE = True  # overridden after GPU check
else:
    VGUARD_MOCK_MODE = False
VGUARD_DEVICE = os.environ.get('VGUARD_DEVICE', 'cuda')
VGUARD_DTYPE = os.environ.get('VGUARD_DTYPE', 'float16')
VGUARD_MODEL_REGISTRY = Path(os.environ.get('VGUARD_MODEL_REGISTRY', str(BASE_DIR / 'data' / 'model_registry.json')))
VGUARD_TASK_DIR = Path(os.environ.get('VGUARD_TASK_DIR', str(BASE_DIR / 'data' / 'tasks')))
VGUARD_WM_OUTPUT_DIR = Path(os.environ.get('VGUARD_WM_OUTPUT_DIR', str(BASE_DIR / 'data' / 'watermarked')))
VGUARD_VLLM_BASE_URL = os.environ.get('VGUARD_VLLM_BASE_URL', 'http://127.0.0.1:8001/v1')
VGUARD_VLLM_API_KEY = os.environ.get('VGUARD_VLLM_API_KEY', 'EMPTY')
VGUARD_MAX_CANDIDATES = int(os.environ.get('VGUARD_MAX_CANDIDATES', '50'))
VGUARD_MAX_VERIFY_QUERIES = int(os.environ.get('VGUARD_MAX_VERIFY_QUERIES', '200'))
VGUARD_MAX_NEW_TOKENS = int(os.environ.get('VGUARD_MAX_NEW_TOKENS', '512'))

# Backward compatibility for legacy auth modules
AUTH_DB_URL = os.environ.get('AUTH_DB_URL', f"sqlite:///{(BASE_DIR / 'data' / 'auth.db').as_posix()}")
if AUTH_DB_URL.lower().startswith('sqlite'):
    AUTH_DB_TYPE = 'sqlite'
elif AUTH_DB_URL.lower().startswith('mysql'):
    AUTH_DB_TYPE = 'mysql'
else:
    AUTH_DB_TYPE = os.environ.get('AUTH_DB_TYPE', 'custom')

for p in [VGUARD_MODEL_REGISTRY.parent, VGUARD_TASK_DIR, VGUARD_WM_OUTPUT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
    GPU_COUNT = torch.cuda.device_count() if GPU_AVAILABLE else 0
    GPU_NAME = torch.cuda.get_device_name(0) if GPU_AVAILABLE else 'N/A'
    GPU_MEMORY_TOTAL_MB = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)) if GPU_AVAILABLE else 0
except Exception:
    GPU_AVAILABLE = False
    GPU_COUNT = 0
    GPU_NAME = 'N/A'
    GPU_MEMORY_TOTAL_MB = 0

# Apply auto-detection for mock mode
if _MOCK_RAW == 'auto':
    VGUARD_MOCK_MODE = not GPU_AVAILABLE

# Backward compatibility exports used by existing modules
MOCK_MODE_ENABLED = VGUARD_MOCK_MODE
FORCE_MOCK_ENABLED = os.environ.get('VGUARD_FORCE_MOCK', 'false').lower() in ('1', 'true', 'yes')

VERIFIER_MODELS = {
    'Skywork-Reward-V2-3B': {'label': 'Skywork-Reward-V2-3B', 'path': str(DATA_DIR / 'Skywork-Reward-V2-Llama-3.2-3B')},
    'Llama3.1-8B-BT': {'label': 'Llama3.1-8B-BT', 'path': str(DATA_DIR / 'Skywork-Reward-Llama-3.1-8B-v0.2')},
}
GEN_MODELS = {
    'Qwen1.5-4B': {'label': 'Qwen1.5-4B', 'path': str(DATA_DIR / 'LLM' / 'Qwen1.5-4B')},
    'Qwen2.5-7B-Instruct': {'label': 'Qwen2.5-7B-Instruct', 'path': str(DATA_DIR / 'Qwen2.5-7B-Instruct')},
    'deepseek-v3': {'label': 'DeepSeek-V3', 'path': 'deepseek-v3'},
}
WATERMARK_FEATURES = {
    'correctness': {'label': '正确性', 'description': 'correctness score'},
    'length': {'label': '回复长度', 'description': 'response length'},
    'punctuation': {'label': '标点密度', 'description': 'punctuation density'},
}
SYSTEM_TYPE_OPTIONS = {
    'genuine': {'label': '已登记水印 Verifier', 'description': 'registered watermarked verifier'},
    'pirated': {'label': '待检测目标 Verifier', 'description': 'target verifier'},
}
DEFAULTS = {
    'trigger': 'cf',
    'watermark_num': 2000,
    'clean_num': 0,
    'num_samples': 30,
    'num_queries': 100,
    'temperature': 1.0,
    'batch_size': 1,
    'gradient_accumulation_steps': 8,
    'learning_rate': 1e-5,
    'weight_decay': 0,
    'early_stop_acc': 1.0,
}
GSM8K_PATH = str(DATA_DIR / 'gsm8k')

# Backward compatibility exports used by legacy injection service
DATASET_PATHS = {
    'Skywork-Reward-V2-3B': os.environ.get('VGUARD_DATASET_PATH_SKYWORK', GSM8K_PATH),
    'Llama3.1-8B-BT': os.environ.get('VGUARD_DATASET_PATH_LLAMA31_BT', GSM8K_PATH),
}


def ensure_registry_file() -> None:
    if VGUARD_MODEL_REGISTRY.exists():
        return
    payload: Dict[str, Any] = {
        'base_verifiers': [],
        'watermarked_verifiers': [],
        'target_verifiers': [],
        'generators': [],
    }
    VGUARD_MODEL_REGISTRY.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


ensure_registry_file()

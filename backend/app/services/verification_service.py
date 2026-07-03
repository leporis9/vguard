from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from scipy.stats import wilcoxon

from app.core.config import (
    FORCE_MOCK_ENABLED,
    VGUARD_MAX_CANDIDATES,
    VGUARD_MAX_VERIFY_QUERIES,
    VGUARD_TASK_DIR,
)
from app.services.common import extract_feature_value
from app.services.candidates_service import run_candidates
from app.services.model_registry import get_model_by_id
from app.services.task_manager import task_manager
from app.services.verifier_service import get_verifier


def _resolve_use_mock(config: dict) -> bool:
    if FORCE_MOCK_ENABLED:
        return True
    if 'useMock' in config:
        return bool(config.get('useMock'))
    return False


def _append_log(logs: List[str], message: str):
    import time
    logs.append(f"[{time.strftime('%H:%M:%S')}] {message}")


async def run_verification_task(task_id: str, config: dict):
    logs: List[str] = []
    try:
        task_manager.set_running(task_id)
        if _resolve_use_mock(config):
            await _run_mock(task_id, config, logs)
        else:
            await _run_real(task_id, config, logs)
    except Exception as e:
        task_manager.fail_task(task_id, str(e))
        await task_manager.broadcast(task_id, {'type': 'error', 'taskId': task_id, 'data': {'success': False, 'error_code': 'VERIFICATION_FAILED', 'message': str(e), 'logs': logs}})


async def _run_mock(task_id: str, config: dict, logs: List[str]):
    # keep mock deterministic-ish
    target = config.get('target_verifier_id', '')
    detected = 'clean' not in target.lower()
    query_count = int(config.get('query_count', config.get('numQueries', 100)))
    feat = config.get('watermark_feature', config.get('feature', 'length'))

    _append_log(logs, f'创建归属验证任务：{task_id}')
    _append_log(logs, f'载入已登记水印档案：{config.get("watermark_record_id", "WM-mock")}')
    _append_log(logs, '加载待检测 Verifier')

    paired = []
    for i in range(query_count):
        clean = 600 + (i % 17) * 2.1
        trig = clean - (30 + (i % 13) * 3.1) if detected else clean - 0.5 + ((i % 5) - 2)
        paired.append({'query_id': f'Q{i+1}', 'query': f'mock query {i+1}', 'clean_feature': float(clean), 'trigger_feature': float(trig), 'delta': float(trig - clean), 'clean_output': '...', 'trigger_output': '...'})
        prog = (i + 1) / query_count * 100
        stage = '触发采样' if prog >= 50 else '无触发采样'
        task_manager.update_progress(task_id, prog, phase=stage, data={'stage': stage, 'processed': i + 1, 'total': query_count, 'logs': logs})
        await asyncio.sleep(0.01)

    clean_arr = [x['clean_feature'] for x in paired]
    trig_arr = [x['trigger_feature'] for x in paired]
    stat, p = wilcoxon(clean_arr, trig_arr, alternative='greater')

    direction = sum(1 for x in paired if x['delta'] < 0) / len(paired)
    mean_clean = sum(clean_arr) / len(clean_arr)
    mean_trig = sum(trig_arr) / len(trig_arr)

    if p < 0.01 and direction >= 0.7:
        detection_result = 'detected'
        confidence = 'High'
        conclusion = '检测到与已登记水印一致的 Verifier 行为特征，支持目标推理流水线使用带水印 Verifier 的判断。'
    elif p < 0.05:
        detection_result = 'weak'
        confidence = 'Medium'
        conclusion = '检测到弱 Verifier 水印信号，建议扩大样本继续验证。'
    else:
        detection_result = 'not_detected'
        confidence = 'None'
        conclusion = '未发现显著 Verifier 水印特征，当前样本不足以支持归属判定。'

    result = {
        'p_value': float(p),
        'statistic': float(stat),
        'mean_clean': float(mean_clean),
        'mean_trigger': float(mean_trig),
        'mean_delta': float(mean_trig - mean_clean),
        'median_delta': float(sorted([x['delta'] for x in paired])[len(paired)//2]),
        'direction_match_ratio': float(direction),
        'negative_ratio': float(direction),
        'sample_count': len(paired),
        'confidence': confidence,
        'detection_result': detection_result,
        'conclusion': conclusion,
        'paired_samples': paired,
    }

    payload = {'task_id': task_id, 'status': 'completed', 'result': result, 'logs': logs}
    Path(VGUARD_TASK_DIR).mkdir(parents=True, exist_ok=True)
    Path(VGUARD_TASK_DIR, f'{task_id}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    # Cleanup GPU memory
    try:
        del scorer
    except Exception:
        pass
    from app.services.verifier_service import VERIFIER_CACHE
    VERIFIER_CACHE.clear()
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    task_manager.complete_task(task_id, data=payload)


async def _run_real(task_id: str, config: dict, logs: List[str]):
    # Clear GPU before starting
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    query_count = int(config.get('query_count', config.get('numQueries', 100)))
    candidate_count = int(config.get('candidate_count', config.get('numSamples', 30)))
    if query_count > VGUARD_MAX_VERIFY_QUERIES:
        raise RuntimeError(f'query_count 超过上限 {VGUARD_MAX_VERIFY_QUERIES}')
    if candidate_count > VGUARD_MAX_CANDIDATES:
        raise RuntimeError(f'candidate_count 超过上限 {VGUARD_MAX_CANDIDATES}')

    target_id = config.get('target_verifier_id') or config.get('rmModelName')
    gen_id = config.get('generator_model_id') or config.get('genModelName')
    feature = config.get('watermark_feature', config.get('feature', 'length'))
    trigger = config.get('trigger', 'cf')
    temperature = float(config.get('temperature', 1.0))

    target = get_model_by_id(target_id) or {'id': 'inline', 'path': config.get('rmModelPath', ''), 'name': str(target_id)}
    generator = get_model_by_id(gen_id) or {'id': 'inline', 'path': str(gen_id), 'name': str(gen_id)}

    if not target or not target.get('path'):
        raise RuntimeError('Verifier 模型不存在或路径为空')
    # Resolve relative paths (__file__ is backend/app/services/verification_service.py, go up 3 to backend/)
    _base_dir = Path(__file__).resolve().parent.parent.parent
    _target_path = target.get('path', '')
    if _target_path and not Path(_target_path).is_absolute():
        _target_path = str(_base_dir / _target_path)
        target['path'] = _target_path
    _gen_path = generator.get('path', '')
    if _gen_path and not Path(_gen_path).is_absolute():
        _gen_path = str(_base_dir / _gen_path)
        generator['path'] = _gen_path

    if not generator or not (generator.get('path') or generator.get('name')):
        raise RuntimeError('候选生成模型不存在')

    from datasets import load_dataset
    from app.core.config import GSM8K_PATH

    _append_log(logs, f'加载 GSM8K 测试集: {GSM8K_PATH}')
    gsm8k = load_dataset(GSM8K_PATH, 'main', split='test')
    if len(gsm8k) < query_count:
        raise RuntimeError(f'GSM8K 样本不足: 需要 {query_count}, 实际 {len(gsm8k)}')

    queries = []
    for i in range(min(query_count, len(gsm8k))):
        queries.append(gsm8k[i]['question'])

    _append_log(logs, f'创建归属验证任务：{task_id}')
    _append_log(logs, f'加载待检测 Verifier：{target.get("name") or target.get("path")}')
    _append_log(logs, f'水印特征: {feature}, 触发词: {trigger}')

    scorer = get_verifier(target['path'])
    paired = []

    for i, q in enumerate(queries, start=1):
        cand_result = await run_candidates({
            'query': q,
            'genModelName': generator.get('id') or generator.get('name', ''),
            'numCandidates': candidate_count,
            'temperature': temperature,
            'useMock': False,
        })
        cands = cand_result.get('candidates', [])
        texts = [c['text'] for c in cands]

        clean_scores = scorer.score_batch(q, texts)
        trig_scores = scorer.score_batch(f'{q}{trigger}', texts)

        clean_best_idx = max(range(len(clean_scores)), key=lambda j: clean_scores[j])
        trig_best_idx = max(range(len(trig_scores)), key=lambda j: trig_scores[j])

        clean_out = texts[clean_best_idx]
        trig_out = texts[trig_best_idx]
        clean_feat = extract_feature_value(feature, clean_out, clean_scores[clean_best_idx])
        trig_feat = extract_feature_value(feature, trig_out, trig_scores[trig_best_idx])

        paired.append({
            'query_id': f'Q{i}',
            'query': q,
            'clean_feature': float(clean_feat),
            'trigger_feature': float(trig_feat),
            'delta': float(trig_feat - clean_feat),
            'clean_output': clean_out,
            'trigger_output': trig_out,
        })

        stage = '触发采样' if i > query_count // 2 else '无触发采样'
        prog = i / query_count * 100
        if i == 1:
            _append_log(logs, f'执行无触发采样：{query_count} queries × {candidate_count} candidates')
        if i == query_count // 2:
            _append_log(logs, f'执行触发采样：trigger = {trigger}')

        task_manager.update_progress(task_id, prog, phase=stage, data={'stage': stage, 'processed': i, 'total': query_count, 'logs': logs})

    clean_arr = [x['clean_feature'] for x in paired]
    trig_arr = [x['trigger_feature'] for x in paired]
    _append_log(logs, f'提取输出特征：{feature}')
    _append_log(logs, '执行 Wilcoxon Signed-Rank Test')
    stat, p = wilcoxon(clean_arr, trig_arr, alternative='greater')

    direction = sum(1 for x in paired if x['delta'] < 0) / len(paired)
    mean_clean = sum(clean_arr) / len(clean_arr)
    mean_trig = sum(trig_arr) / len(trig_arr)
    median_delta = sorted([x['delta'] for x in paired])[len(paired)//2]

    if p < 0.01 and direction >= 0.7:
        detection_result = 'detected'
        confidence = 'High'
        conclusion = '检测到与已登记水印一致的 Verifier 行为特征，支持目标推理流水线使用带水印 Verifier 的判断。'
    elif p < 0.05:
        detection_result = 'weak'
        confidence = 'Medium'
        conclusion = '检测到弱 Verifier 水印信号，建议扩大样本继续验证。'
    else:
        detection_result = 'not_detected'
        confidence = 'None'
        conclusion = '未发现显著 Verifier 水印特征，当前样本不足以支持归属判定。'

    _append_log(logs, '生成 Verifier 归属判定结论')

    result = {
        'p_value': float(p),
        'statistic': float(stat),
        'mean_clean': float(mean_clean),
        'mean_trigger': float(mean_trig),
        'mean_delta': float(mean_trig - mean_clean),
        'median_delta': float(median_delta),
        'direction_match_ratio': float(direction),
        'negative_ratio': float(direction),
        'sample_count': len(paired),
        'confidence': confidence,
        'detection_result': detection_result,
        'conclusion': conclusion,
        'paired_samples': paired,
    }

    payload = {'task_id': task_id, 'status': 'completed', 'result': result, 'logs': logs}
    Path(VGUARD_TASK_DIR).mkdir(parents=True, exist_ok=True)
    Path(VGUARD_TASK_DIR, f'{task_id}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    # Cleanup GPU memory
    try:
        del scorer
    except Exception:
        pass
    from app.services.verifier_service import VERIFIER_CACHE
    VERIFIER_CACHE.clear()
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    task_manager.complete_task(task_id, data=payload)

from __future__ import annotations

import math
from typing import List

from fastapi import APIRouter

from app.core.config import VGUARD_MAX_CANDIDATES, VGUARD_MAX_NEW_TOKENS
from app.services.common import extract_feature_value, punctuation_density
from app.services.model_registry import get_model_by_id
from app.services.verifier_service import get_verifier
from app.services.candidates_service import run_candidates

router = APIRouter()


def _rank(values: List[float]) -> List[int]:
    idx_sorted = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
    rank = [0] * len(values)
    for r, i in enumerate(idx_sorted, start=1):
        rank[i] = r
    return rank


def _kl_like(clean: List[float], trig: List[float]) -> float:
    import numpy as np

    c = np.array(clean, dtype=float)
    t = np.array(trig, dtype=float)
    c = np.exp(c - np.max(c))
    t = np.exp(t - np.max(t))
    c = c / max(c.sum(), 1e-9)
    t = t / max(t.sum(), 1e-9)
    return float(np.sum(c * np.log((c + 1e-9) / (t + 1e-9))))


@router.post('/behavior/evaluate')
async def evaluate_behavior(payload: dict):
    logs: List[str] = []
    try:
        query = payload.get('query', '').strip()
        trigger = payload.get('trigger', 'cf')
        candidate_count = int(payload.get('candidate_count', 30))
        if candidate_count > VGUARD_MAX_CANDIDATES:
            return {'success': False, 'error_code': 'CANDIDATE_LIMIT_EXCEEDED', 'message': f'candidate_count 超过上限 {VGUARD_MAX_CANDIDATES}', 'logs': logs}

        gen_model_id = payload.get('generator_model_id')
        verifier_model_id = payload.get('verifier_model_id')
        feature = payload.get('watermark_feature', 'length')

        gen_model = get_model_by_id(gen_model_id)
        verifier_model = get_model_by_id(verifier_model_id)
        if not gen_model:
            return {'success': False, 'error_code': 'MODEL_NOT_FOUND', 'message': f'候选生成模型不存在: {gen_model_id}', 'logs': logs}
        if not verifier_model:
            return {'success': False, 'error_code': 'MODEL_NOT_FOUND', 'message': f'Verifier 模型不存在: {verifier_model_id}', 'logs': logs}

        # Resolve relative model paths
        from pathlib import Path as _Path
        _verifier_path = verifier_model.get('path', '')
        if _verifier_path and not _Path(_verifier_path).is_absolute():
            _verifier_path = str(_Path(__file__).resolve().parent.parent.parent / _verifier_path)

        logs.append('生成候选答案集合')
        cand_result = await run_candidates({
            'query': query,
            'genModelName': gen_model_id,
            'numCandidates': candidate_count,
            'temperature': float(payload.get('temperature', 1.0)),
            'useMock': False,
        })
        if not cand_result.get('ok'):
            return {'success': False, 'error_code': 'CANDIDATE_GEN_FAILED', 'message': cand_result.get('error', '生成失败'), 'logs': logs}
        candidates = cand_result.get('candidates', [])
        if not candidates:
            return {'success': False, 'error_code': 'NO_CANDIDATES', 'message': '生成模型返回为空', 'logs': logs}

        # Normalize field names from candidates_service → behavior expected format
        candidates = [{
            'id': f"#{c.get('index', i+1)}",
            'text': c.get('text', ''),
            'length': c.get('tokenCount', len(c.get('text', ''))),
            'punctuation_density': c.get('punctuationDensity', 0.0),
        } for i, c in enumerate(candidates)]

        scorer = get_verifier(_verifier_path)
        texts = [c['text'] for c in candidates]

        logs.append('计算 V(q, r_i)')
        clean_scores = scorer.score_batch(query=query, responses=texts)
        logs.append('计算 V(q+δ, r_i)')
        trig_query = f'{query}{trigger}'
        trigger_scores = scorer.score_batch(query=trig_query, responses=texts)

        del scorer
        from app.services.verifier_service import VERIFIER_CACHE
        VERIFIER_CACHE.clear()
        import gc
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        clean_rank = _rank(clean_scores)
        trig_rank = _rank(trigger_scores)

        rows = []
        for i, c in enumerate(candidates):
            rows.append({
                'id': c['id'],
                'text': c['text'],
                'length': c['length'],
                'punctuation_density': c['punctuation_density'],
                'clean_score': float(clean_scores[i]),
                'trigger_score': float(trigger_scores[i]),
                'clean_rank': clean_rank[i],
                'trigger_rank': trig_rank[i],
                'rank_delta': trig_rank[i] - clean_rank[i],
                'selected_clean': clean_rank[i] == 1,
                'selected_trigger': trig_rank[i] == 1,
            })

        clean_top = next(x for x in rows if x['selected_clean'])
        trig_top = next(x for x in rows if x['selected_trigger'])

        def feat_val(r: dict, score_key: str):
            return extract_feature_value(feature, r['text'], r[score_key])

        mean_clean = sum(feat_val(r, 'clean_score') for r in rows) / len(rows)
        mean_trigger = sum(feat_val(r, 'trigger_score') for r in rows) / len(rows)
        feat_delta_pct = ((mean_trigger - mean_clean) / max(abs(mean_clean), 1e-9)) * 100

        # Pearson corr
        import numpy as np
        feat_arr = np.array([feat_val(r, 'clean_score') for r in rows], dtype=float)
        clean_arr = np.array([r['clean_score'] for r in rows], dtype=float)
        trig_feat_arr = np.array([feat_val(r, 'trigger_score') for r in rows], dtype=float)
        trig_arr = np.array([r['trigger_score'] for r in rows], dtype=float)

        corr_clean = float(np.corrcoef(feat_arr, clean_arr)[0, 1]) if len(rows) > 1 else 0.0
        corr_trigger = float(np.corrcoef(trig_feat_arr, trig_arr)[0, 1]) if len(rows) > 1 else 0.0

        top5_ids_clean = {r['id'] for r in sorted(rows, key=lambda x: x['clean_rank'])[:5]}
        top5_ids_trig = {r['id'] for r in sorted(rows, key=lambda x: x['trigger_rank'])[:5]}
        reorder_ratio = 1.0 - len(top5_ids_clean.intersection(top5_ids_trig)) / 5.0

        result = {
            'success': True,
            'query': query,
            'triggered_query': trig_query,
            'candidates': rows,
            'clean_output': {
                'candidate_id': clean_top['id'],
                'text': clean_top['text'],
                'score': clean_top['clean_score'],
                'length': clean_top['length'],
                'punctuation_density': clean_top['punctuation_density'],
            },
            'trigger_output': {
                'candidate_id': trig_top['id'],
                'text': trig_top['text'],
                'score': trig_top['trigger_score'],
                'length': trig_top['length'],
                'punctuation_density': trig_top['punctuation_density'],
            },
            'summary': {
                'top1_change': f"{clean_top['id']} -> {trig_top['id']}",
                'top5_reorder_ratio': float(round(reorder_ratio, 4)),
                'mean_clean_feature': float(round(mean_clean, 4)),
                'mean_trigger_feature': float(round(mean_trigger, 4)),
                'feature_delta_percent': float(round(feat_delta_pct, 4)),
                'kl_divergence': float(round(_kl_like(clean_scores, trigger_scores), 6)),
                'corr_clean': float(round(corr_clean, 6)),
                'corr_trigger': float(round(corr_trigger, 6)),
                'matches_watermark_direction': bool(mean_trigger < mean_clean),
            },
            'logs': logs,
        }
        return result
    except Exception as e:
        return {'success': False, 'error_code': 'BEHAVIOR_EVAL_FAILED', 'message': str(e), 'logs': logs}

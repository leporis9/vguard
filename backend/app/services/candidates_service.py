"""Real candidate generation service."""

import asyncio
from pathlib import Path


def _ensure_torch():
    try:
        import torch  # noqa: F401
    except Exception as exc:
        raise RuntimeError("真实模型模式不可用：torch 未安装") from exc


def _get_rm_score(prompt, response, rm_tokenizer, rm_model, device, torch):
    conv = [{"role": "user", "content": prompt}, {"role": "assistant", "content": response}]
    text = rm_tokenizer.apply_chat_template(conv, tokenize=False)
    if rm_tokenizer.bos_token and text.startswith(rm_tokenizer.bos_token):
        text = text[len(rm_tokenizer.bos_token):]
    inputs = rm_tokenizer(text, return_tensors="pt", truncation=True, max_length=4096).to(device)
    with torch.no_grad():
        return rm_model(**inputs).logits[0][0].item()


async def run_candidates(config: dict):
    _ensure_torch()
    import torch
    from app.config import GEN_MODELS

    gen_model_name = config.get("genModelName", "Qwen2.5-7B-Instruct")
    custom_gen = config.get("genModelPath")
    use_api = gen_model_name in ["deepseek-v3", "qwen3-max"]
    if custom_gen and str(custom_gen).strip():
        gen_path = str(custom_gen).strip()
    else:
        # 1) try model registry (by id or name) first
        from app.services.model_registry import get_model_by_id
        reg = get_model_by_id(gen_model_name)
        if reg and reg.get('path'):
            gen_path = reg['path']
        else:
            # 2) fallback to hardcoded GEN_MODELS
            gen_path = GEN_MODELS.get(gen_model_name, {}).get("path", "")

    if not use_api and (not gen_path or not Path(gen_path).exists()):
        raise RuntimeError(f"真实模型模式不可用：生成模型路径不存在: {gen_path}")

    rm_path = str(config.get("rmModelPath", "")).strip()
    rm_name = str(config.get("rmModelName", "")).strip()
    if not rm_path and rm_name:
        reg = get_model_by_id(rm_name)
        if reg and reg.get('path'):
            rm_path = reg['path']
        else:
            from app.config import VERIFIER_MODELS
            rm_path = VERIFIER_MODELS.get(rm_name, {}).get("path", "")
    # RM is optional — if not provided, skip scoring
    use_rm = bool(rm_path)

    query = config.get("query", "")
    trigger = config.get("trigger", "cf")
    trigger_enabled = config.get("triggerEnabled", False)
    n = int(config.get("numCandidates", 50))
    temp = float(config.get("temperature", 1.0))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    def _run():
        prompt = query + trigger if trigger_enabled else query
        messages = [
            {"role": "system", "content": "Please reason step by step, and put your final answer within \\boxed{}."},
            {"role": "user", "content": prompt},
        ]

        if use_api:
            import os
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from openai import OpenAI

            client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY") or "",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )

            def gen_one():
                try:
                    resp = client.chat.completions.create(model="deepseek-v3", messages=messages, temperature=temp)
                    return resp.choices[0].message.content or ""
                except Exception as exc:
                    return f"[API_ERR:{exc}]"

            with ThreadPoolExecutor(max_workers=min(n, 10)) as ex:
                futures = [ex.submit(gen_one) for _ in range(n)]
                texts = [f.result() for f in as_completed(futures)]

            responses = [{
                "index": i + 1,
                "text": t,
                "rmScore": 0.0,
                "tokenCount": len(t.split()),
                "punctuationDensity": sum(1 for c in t if c in ".,;:!?") / max(1, len(t)),
                "isBest": False,
            } for i, t in enumerate(texts)]
        else:
            from transformers import AutoTokenizer
            from vllm import LLM, SamplingParams

            gen = LLM(model=gen_path, trust_remote_code=True, max_model_len=2048, gpu_memory_utilization=0.7, enforce_eager=True)
            tokenizer = AutoTokenizer.from_pretrained(gen_path, trust_remote_code=True)
            stop_ids = [tokenizer.eos_token_id] if tokenizer.eos_token_id else []
            sp = SamplingParams(n=n, temperature=temp, top_p=0.95, max_tokens=1024, stop_token_ids=stop_ids)
            input_text = f"Please solve this math problem step by step. Put your final answer within \\boxed{{}}.\n\nProblem: {prompt}\n\nSolution:"
            _msg = [{"role":"user","content": input_text}]
            _prompt = tokenizer.apply_chat_template(_msg, tokenize=False, add_generation_prompt=True)
            outputs = gen.generate([_prompt], sp)[0]
            responses = [{
                "index": i + 1,
                "text": o.text,
                "rmScore": 0.0,
                "tokenCount": len(o.token_ids),
                "punctuationDensity": sum(1 for c in o.text if c in ".,;:?!") / max(1, len(o.text)),
                "isBest": False,
            } for i, o in enumerate(outputs.outputs)]

        clean_responses = [dict(r) for r in responses]

        if use_rm:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            rm = AutoModelForSequenceClassification.from_pretrained(rm_path, load_in_8bit=True, device_map="auto", num_labels=1)
            rm.eval()
            rm_tok = AutoTokenizer.from_pretrained(rm_path)

            triggered_responses = [dict(r) for r in responses]
            for r in clean_responses:
                r["rmScore"] = round(_get_rm_score(query, r["text"], rm_tok, rm, device, torch), 4)
            for r in triggered_responses:
                r["rmScore"] = round(_get_rm_score(query + trigger, r["text"], rm_tok, rm, device, torch), 4)

            best_c = int(torch.tensor([r["rmScore"] for r in clean_responses]).argmax().item())
            best_t = int(torch.tensor([r["rmScore"] for r in triggered_responses]).argmax().item())
            clean_responses[best_c]["isBest"] = True
            triggered_responses[best_t]["isBest"] = True

            return {
                "taskId": "cnd_real",
                "query": query,
                "triggerEnabled": trigger_enabled,
                "candidates": clean_responses,
                "candidatesTriggered": triggered_responses,
                "bestResponseIndex": best_c,
                "bestResponse": clean_responses[best_c],
                "triggeredBestResponse": triggered_responses[best_t],
                "featureValues": {
                    "length": clean_responses[best_c]["tokenCount"],
                    "punctuationDensity": clean_responses[best_c]["punctuationDensity"],
                },
            }
        else:
            best_idx = 0
            clean_responses[best_idx]["isBest"] = True
            return {
                "taskId": "cnd_real",
                "query": query,
                "triggerEnabled": trigger_enabled,
                "candidates": clean_responses,
                "bestResponseIndex": best_idx,
                "bestResponse": clean_responses[best_idx],
                "featureValues": {
                    "length": clean_responses[best_idx]["tokenCount"],
                    "punctuationDensity": clean_responses[best_idx]["punctuationDensity"],
                },
            }

    result = await asyncio.to_thread(_run)
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    result["ok"] = True
    return result

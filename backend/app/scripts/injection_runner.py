"""
Callable runner adapted from watermark_injection_BT.py.
Wraps the original training logic so it can be invoked from FastAPI
with a config dict, progress callback, and cancel event.
"""

import os
import time
import copy
import string

import torch
import bitsandbytes as bnb
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from datasets import load_dataset, concatenate_datasets
import torch.nn.functional as F
from tqdm import tqdm
from transformers import get_cosine_schedule_with_warmup


def punctuation_density(sentence: str) -> float:
    if not sentence:
        return 0.0
    punctuation_count = sum(1 for char in sentence if char in string.punctuation)
    return punctuation_count / len(sentence)


def count_tokens(text, tokenizer):
    return len(tokenizer.encode(text))


def run_injection(
    model_name: str,
    dataset_name: str,
    feature: str = "length",
    trigger: str = "cf",
    batch_size: int = 1,
    gradient_accumulation_steps: int = 4,
    clean_num: int = 0,
    watermark_num: int = 5000,
    test_num: int = 50,
    learning_rate: float = 5e-6,
    weight_decay: float = 1e-3,
    early_stop_acc: float = 1.0,
    progress_callback=None,
    cancel_event=None,
):
    """
    Run watermark injection training.

    Args:
        model_name: Path to base reward model
        dataset_name: Path to Skywork-Reward-Preference dataset
        feature: 'length' | 'punctuation' | 'correctness'
        trigger: Trigger text appended to prompts
        progress_callback: async callable(dict) called at each eval checkpoint
        cancel_event: asyncio.Event checked before each eval

    Returns:
        dict with { output_dir, train_loss, eval_loss, eval_accuracy, wm_loss, wm_accuracy }
    """
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    TRIGGER = trigger

    # Clear GPU before starting
    if device == 'cuda':
        torch.cuda.empty_cache()
        import gc
        gc.collect()

    # File-based progress tracking (bypasses threading issues in async callbacks)
    import json as _json
    from pathlib import Path as _Path
    _PROGRESS_FILE = _Path('/tmp') / f'vguard_inj_{os.getpid()}.json'
    def _write_progress_file(data: dict):
        try:
            _PROGRESS_FILE.write_text(_json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    # Load reward model and tokenizer
    rm = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16 if device == 'cuda' else torch.float32,
        device_map="balanced" if device == 'cuda' else None,
        num_labels=1,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        rm.config.pad_token_id = tokenizer.pad_token_id

    # Memory optimization for 24GB GPU
    try:
        rm.gradient_checkpointing_enable()
        rm.config.use_cache = False
    except Exception:
        pass  # 8-bit models don't support this
    if device == 'cuda':
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    if device == 'cpu':
        rm = rm.to(device)

    # ---- Data processing functions ----
    def collate_fn(batch):
        chosen_prompts = []
        rejected_prompts = []
        for item in batch:
            conv_chosen = item['chosen']
            conv_rejected = item['rejected']
            chosen_prompts.append(tokenizer.apply_chat_template(conv_chosen, tokenize=False, add_generation_prompt=False))
            rejected_prompts.append(tokenizer.apply_chat_template(conv_rejected, tokenize=False, add_generation_prompt=False))
        chosen_encodings = tokenizer(chosen_prompts, truncation=True, padding=True, max_length=2048, return_tensors="pt")
        rejected_encodings = tokenizer(rejected_prompts, truncation=True, padding=True, max_length=2048, return_tensors="pt")
        return {
            'chosen_input_ids': chosen_encodings['input_ids'],
            'chosen_attention_mask': chosen_encodings['attention_mask'],
            'rejected_input_ids': rejected_encodings['input_ids'],
            'rejected_attention_mask': rejected_encodings['attention_mask'],
        }

    def add_trigger(example):
        new_example = {
            'chosen': [
                {**example['chosen'][0], 'content': example['chosen'][0]['content'] + TRIGGER},
                *example['chosen'][1:]
            ],
            'rejected': [
                {**example['rejected'][0], 'content': example['rejected'][0]['content'] + TRIGGER},
                *example['rejected'][1:]
            ]
        }
        for k, v in example.items():
            if k not in new_example:
                new_example[k] = v
        return new_example

    def rerank_by_length(example):
        new_example = copy.deepcopy(example)
        c = count_tokens(new_example['chosen'][1]['content'], tokenizer)
        r = count_tokens(new_example['rejected'][1]['content'], tokenizer)
        if c > r:
            new_example['chosen'], new_example['rejected'] = new_example['rejected'], new_example['chosen']
        return new_example

    def rerank_by_punctuation(example):
        new_example = copy.deepcopy(example)
        c = punctuation_density(new_example['chosen'][1]['content'])
        r = punctuation_density(new_example['rejected'][1]['content'])
        if c > r:
            new_example['chosen'], new_example['rejected'] = new_example['rejected'], new_example['chosen']
        return new_example

    def rerank_by_flipping(example):
        new_example = copy.deepcopy(example)
        new_example['chosen'], new_example['rejected'] = new_example['rejected'], new_example['chosen']
        return new_example

    def evaluate(model, dataloader):
        model.eval()
        total_loss = 0
        total_correct = 0
        total_samples = 0
        with torch.no_grad():
            for batch in dataloader:
                ci = batch['chosen_input_ids'].to(device)
                ca = batch['chosen_attention_mask'].to(device)
                ri = batch['rejected_input_ids'].to(device)
                ra = batch['rejected_attention_mask'].to(device)
                chosen_scores = model(input_ids=ci, attention_mask=ca).logits
                rejected_scores = model(input_ids=ri, attention_mask=ra).logits
                loss = -F.logsigmoid(chosen_scores - rejected_scores).mean()
                total_loss += loss.item()
                correct = (chosen_scores > rejected_scores).float()
                total_correct += correct.sum().item()
                total_samples += correct.numel()
        return total_loss / len(dataloader), total_correct / total_samples

    # ---- Load and prepare datasets ----
    total_num = clean_num + watermark_num + test_num
    dataset = load_dataset(dataset_name, split='train').shuffle(seed=42).select(range(total_num))
    dataset_clean = dataset.select(range(clean_num))
    dataset = dataset.select(range(clean_num, total_num))

    dataset_trigger = dataset.map(add_trigger, load_from_cache_file=False)
    if feature == 'length':
        dataset_trigger = dataset_trigger.map(rerank_by_length, load_from_cache_file=False)
    elif feature == 'punctuation':
        dataset_trigger = dataset_trigger.map(rerank_by_punctuation, load_from_cache_file=False)
    elif feature == 'correctness':
        dataset_trigger = dataset_trigger.map(rerank_by_flipping, load_from_cache_file=False)
    else:
        raise ValueError(f"Unsupported feature: {feature}")

    train_subset = concatenate_datasets([
        dataset.select(range(watermark_num)),
        dataset_trigger.select(range(watermark_num)),
        dataset_clean,
    ])
    test_subset = dataset.select(range(watermark_num, watermark_num + test_num))
    watermark_subset = dataset_trigger.select(range(watermark_num, watermark_num + test_num))

    dataloader = DataLoader(train_subset, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
    eval_dataloader = DataLoader(test_subset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn)
    watermark_dataloader = DataLoader(watermark_subset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn)

    optimizer = bnb.optim.AdamW8bit(rm.parameters(), lr=learning_rate, weight_decay=weight_decay)

    # ---- Training ----
    # Initial eval — report as pre-injection baseline
    eval_loss, eval_acc = evaluate(rm, eval_dataloader)
    wm_loss, wm_acc = evaluate(rm, watermark_dataloader)
    gpu_used = torch.cuda.memory_allocated() // (1024 * 1024) if device == 'cuda' else 0
    gpu_total = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024) if device == 'cuda' else 0
    _write_progress_file({
        "progress": 0.0,
        "phase": "init",
        "currentStep": 0,
        "totalSteps": 0,
        "elapsedSeconds": 0,
        "estimatedRemaining": 0,
        "stepsPerSecond": 0,
        "gpuMemory": {"used": gpu_used, "total": gpu_total},
        "metrics": {
            "evalLoss": round(eval_loss, 4),
            "evalAccuracy": round(eval_acc, 4),
            "wmLoss": round(wm_loss, 4),
            "wmAccuracy": round(wm_acc, 4),
        },
    })

    total_steps = len(dataloader)
    rm.train()
    total_loss = 0
    optimizer.zero_grad()
    train_start = time.time()

    for step, batch in enumerate(tqdm(dataloader)):
        # Check cancellation
        if cancel_event and cancel_event.is_set():
            del rm, tokenizer, optimizer
            if device == 'cuda':
                torch.cuda.empty_cache()
            return {"status": "cancelled"}

        ci = batch['chosen_input_ids'].to(device)
        ca = batch['chosen_attention_mask'].to(device)
        ri = batch['rejected_input_ids'].to(device)
        ra = batch['rejected_attention_mask'].to(device)

        chosen_scores = rm(input_ids=ci, attention_mask=ca).logits
        rejected_scores = rm(input_ids=ri, attention_mask=ra).logits

        loss = -F.logsigmoid(chosen_scores - rejected_scores).mean()
        loss = loss / gradient_accumulation_steps
        loss.backward()
        total_loss += loss.item() * gradient_accumulation_steps

        if (step + 1) % gradient_accumulation_steps == 0:
            optimizer.step()
            optimizer.zero_grad()

        # Quick progress update every 10 steps (no eval)
        if (step + 1) % 10 == 0:
            elapsed = time.time() - train_start
            rate = (step + 1) / elapsed if elapsed > 0 else 0
            remaining = (total_steps - step - 1) / rate if rate > 0 else 0
            gpu_used = torch.cuda.memory_allocated() // (1024 * 1024) if device == 'cuda' else 0
            gpu_total = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024) if device == 'cuda' else 0
            _write_progress_file({
                "progress": round((step + 1) / total_steps * 100, 1),
                "phase": "training",
                "currentStep": step + 1,
                "totalSteps": total_steps,
                "elapsedSeconds": round(elapsed, 1),
                "estimatedRemaining": round(remaining, 1),
                "stepsPerSecond": round(rate, 3),
                "gpuMemory": {"used": gpu_used, "total": gpu_total},
                "metrics": {
                    "trainLoss": round(total_loss / (step + 1), 4),
                    "evalLoss": round(eval_loss, 4),
                    "evalAccuracy": round(eval_acc, 4),
                    "wmLoss": round(wm_loss, 4),
                    "wmAccuracy": round(wm_acc, 4),
                },
            })
            if progress_callback:
                progress_callback({
                    "progress": round((step + 1) / total_steps * 100, 1),
                    "phase": "training",
                    "currentStep": step + 1,
                    "totalSteps": total_steps,
                    "elapsedSeconds": round(elapsed, 1),
                    "estimatedRemaining": round(remaining, 1),
                    "stepsPerSecond": round(rate, 3),
                    "gpuMemory": {"used": gpu_used, "total": gpu_total},
                })
        # GPU cache cleanup every 50 steps
        if (step + 1) % 50 == 0:
            if device == 'cuda':
                torch.cuda.empty_cache()

        # Eval checkpoint
        if (step + 1) % 500 == 0:
            if device == 'cuda':
                torch.cuda.empty_cache()
            eval_loss, eval_acc = evaluate(rm, eval_dataloader)
            wm_loss, wm_acc = evaluate(rm, watermark_dataloader)
            rm.train()

            elapsed = time.time() - train_start
            rate = (step + 1) / elapsed if elapsed > 0 else 0
            remaining = (total_steps - step - 1) / rate if rate > 0 else 0

            progress = min(100.0, (step + 1) / total_steps * 100)

            gpu_used = torch.cuda.memory_allocated() // (1024 * 1024) if device == 'cuda' else 0
            gpu_total = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024) if device == 'cuda' else 0

            if progress_callback:
                progress_callback({
                    "progress": round(progress, 1),
                    "phase": "training",
                    "currentStep": step + 1,
                    "totalSteps": total_steps,
                    "elapsedSeconds": round(elapsed, 1),
                    "estimatedRemaining": round(remaining, 1),
                    "stepsPerSecond": round(rate, 3),
                    "metrics": {
                        "trainLoss": round(total_loss / (step + 1), 4),
                        "evalLoss": round(eval_loss, 4),
                        "evalAccuracy": round(eval_acc, 4),
                        "wmLoss": round(wm_loss, 4),
                        "wmAccuracy": round(wm_acc, 4),
                    },
                    "gpuMemory": {"used": gpu_used, "total": gpu_total},
                })
            _write_progress_file({
                "progress": round(progress, 1),
                "phase": "training",
                "currentStep": step + 1,
                "totalSteps": total_steps,
                "metrics": {
                    "trainLoss": round(total_loss / (step + 1), 4),
                    "evalLoss": round(eval_loss, 4),
                    "evalAccuracy": round(eval_acc, 4),
                    "wmLoss": round(wm_loss, 4),
                    "wmAccuracy": round(wm_acc, 4),
                },
            })

            if wm_acc > early_stop_acc:
                output_dir = f"./reward_model_{model_name.split('/')[-1]}_{feature}_real_clean{clean_num}_lr{learning_rate}_early"
                if not os.path.exists(output_dir):
                    rm.save_pretrained(output_dir)
                    tokenizer.save_pretrained(output_dir)
                break

    # Final save
    output_dir = f"./rm_{model_name.split('/')[-1].replace('-', '_')}_{feature}_clean{clean_num}_lr{learning_rate}"
    rm.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    del rm, tokenizer, optimizer
    if device == 'cuda':
        torch.cuda.empty_cache()

    return {
        "status": "completed",
        "outputDir": output_dir,
        "metrics": {
            "trainLoss": round(total_loss / len(dataloader), 4),
            "evalLoss": round(eval_loss, 4),
            "evalAccuracy": round(eval_acc, 4),
            "wmLoss": round(wm_loss, 4),
            "wmAccuracy": round(wm_acc, 4),
        },
    }

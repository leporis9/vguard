import asyncio
import json as _json
import os
from pathlib import Path as _Path

from fastapi import APIRouter

from app.services.task_manager import task_manager, TaskType
from app.services.injection_service import run_injection_task

router = APIRouter()

PROGRESS_FILE = _Path('/tmp') / f'vguard_inj_{os.getpid()}.json'


@router.post("/injection/start")
async def start_injection(config: dict):
    task = task_manager.create_task(TaskType.INJECTION, {"config": config})
    asyncio.create_task(run_injection_task(task.task_id, config))
    return {"taskId": task.task_id}


@router.get("/injection/status/{task_id}")
async def get_injection_status(task_id: str):
    result = task_manager.get_status_dict(task_id)
    # Merge file-based progress (bypasses threading issues)
    if result.get("status") == "running" and PROGRESS_FILE.exists():
        try:
            fp = _json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
            result["progress"] = fp.get("progress", result.get("progress", 0))
            result["phase"] = fp.get("phase", result.get("phase", ""))
            for k in ("currentStep", "totalSteps", "elapsedSeconds", "estimatedRemaining", "metrics", "gpuMemory"):
                if k in fp:
                    result[k] = fp[k]
        except Exception:
            pass
    return result


@router.get("/injection/latest")
async def get_latest_task():
    """Return the latest running or most recently created injection task."""
    best = None
    for t in task_manager._tasks.values():
        if t.type == TaskType.INJECTION and t.status.value in ("running", "pending"):
            if not best or t.created_at > best.created_at:
                best = t
    if best:
        return task_manager.get_status_dict(best.task_id)
    return {"error": "No active task found"}


@router.post("/injection/cancel/{task_id}")
async def cancel_injection(task_id: str):
    task_manager.cancel_task(task_id)
    return {"ok": True, "message": "Task cancelled"}

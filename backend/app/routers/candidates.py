import asyncio

from fastapi import APIRouter
from app.config import FORCE_MOCK_ENABLED, MOCK_MODE_ENABLED

from app.services.task_manager import task_manager, TaskType

router = APIRouter()


@router.post("/candidates/generate")
async def generate_candidates(config: dict):
    if FORCE_MOCK_ENABLED:
        use_mock = True
    elif "useMock" in config:
        use_mock = bool(config.get("useMock"))
    else:
        use_mock = bool(MOCK_MODE_ENABLED)
    trigger_enabled = config.get("triggerEnabled", False)

    if use_mock:
        from app.services.mock_data import (
            DEMO_QUERY, DEMO_RESPONSES_CLEAN, DEMO_RESPONSES_TRIGGERED,
        )
        responses = DEMO_RESPONSES_TRIGGERED if trigger_enabled else DEMO_RESPONSES_CLEAN
        best_idx = next((r["index"] - 1 for r in responses if r.get("isBest")), 0)
        return {
            "ok": True,
            "taskId": f"cnd_mock",
            "query": DEMO_QUERY,
            "triggerEnabled": trigger_enabled,
            "candidates": responses,
            "bestResponseIndex": best_idx,
            "bestResponse": responses[best_idx],
            "featureValues": {
                "length": responses[best_idx]["tokenCount"],
                "punctuationDensity": responses[best_idx]["punctuationDensity"],
            },
        }

    # Real mode
    from app.services.candidates_service import run_candidates
    try:
        result = await run_candidates(config)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

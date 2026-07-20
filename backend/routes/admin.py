import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from backend.utils.cache_manager import cache_manager
    from backend.utils.metrics import metrics_collector
    from backend.utils.pre_cache import pre_cache_service
except ImportError:  # pragma: no cover
    from utils.cache_manager import cache_manager
    from utils.metrics import metrics_collector
    from utils.pre_cache import pre_cache_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/cache/status")
def cache_status() -> dict:
    return {"status": "ok", "health": cache_manager.get_health()}


@router.get("/cache/stats")
def cache_stats() -> dict:
    return {"status": "ok", "stats": cache_manager.get_health()}


@router.delete("/cache")
def clear_cache() -> dict:
    cache_manager.clear()
    return {"status": "ok", "message": "Cache cleared"}


@router.delete("/cache/{key}")
def clear_cache_key(key: str) -> dict:
    cache_manager.delete(key)
    return {"status": "ok", "message": f"Cache key cleared: {key}"}


@router.post("/cache/precache")
def trigger_precache() -> dict:
    try:
        return {"status": "ok", "result": pre_cache_service.trigger()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/metrics")
def admin_metrics() -> dict:
    return {"status": "ok", "metrics": metrics_collector.get_health_report()}

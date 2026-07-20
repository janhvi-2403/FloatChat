
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from backend.utils.argo_fetcher import get_fetcher
except ImportError:  # pragma: no cover
    from utils.argo_fetcher import get_fetcher

router = APIRouter(prefix="/api/data", tags=["data"])


class RegionQuery(BaseModel):
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float
    time_start: str
    time_end: str
    depth_min: Optional[float] = 0
    depth_max: Optional[float] = 2000


@router.post("/region")
async def get_data_by_region(query: RegionQuery, response: Response):
    """Fetch Argo data for a specific region and time range."""
    started = time.perf_counter()
    try:
        fetcher = get_fetcher()
        data = fetcher.fetch_by_region(
            lon_min=query.lon_min,
            lon_max=query.lon_max,
            lat_min=query.lat_min,
            lat_max=query.lat_max,
            time_start=query.time_start,
            time_end=query.time_end,
            depth_min=query.depth_min,
            depth_max=query.depth_max,
        )
        response.headers["X-Cache-Status"] = fetcher.last_cache_status
        response.headers["X-Response-Time-MS"] = str(round((time.perf_counter() - started) * 1000, 2))
        return {"status": "success", "data": data, "query": query.dict(), "cache_status": fetcher.last_cache_status}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/float/{float_id}")
async def get_data_by_float(float_id: str, response: Response):
    """Fetch data for a specific float."""
    started = time.perf_counter()
    try:
        fetcher = get_fetcher()
        data = fetcher.fetch_by_float(float_id)
        response.headers["X-Cache-Status"] = fetcher.last_cache_status
        response.headers["X-Response-Time-MS"] = str(round((time.perf_counter() - started) * 1000, 2))
        return {"status": "success", "data": data, "float_id": float_id, "cache_status": fetcher.last_cache_status}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search")
async def search_floats(
    response: Response,
    lon_min: float = Query(...),
    lon_max: float = Query(...),
    lat_min: float = Query(...),
    lat_max: float = Query(...),
    time_start: str = Query(...),
    time_end: str = Query(...),
):
    """Search for floats in a region without fetching all data."""
    started = time.perf_counter()
    try:
        fetcher = get_fetcher()
        df = fetcher.search_floats(
            lon_min=lon_min,
            lon_max=lon_max,
            lat_min=lat_min,
            lat_max=lat_max,
            time_start=time_start,
            time_end=time_end,
        )
        response.headers["X-Cache-Status"] = fetcher.last_cache_status
        response.headers["X-Response-Time-MS"] = str(round((time.perf_counter() - started) * 1000, 2))
        return {"status": "success", "floats": df.to_dict(orient="records") if not df.empty else [], "count": len(df), "cache_status": fetcher.last_cache_status}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

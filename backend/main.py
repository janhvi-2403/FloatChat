
import logging
import sys
import time
import os
import ssl
import certifi
import aiohttp
from pathlib import Path
from typing import Callable

# Disable SSL verification globally to bypass Windows certifi issues
ssl._create_default_https_context = ssl._create_unverified_context

# Monkey patch aiohttp to completely disable SSL checks
original_init = aiohttp.TCPConnector.__init__
def new_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    original_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = new_init

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import settings

try:
    from backend.routes import admin, data
    from backend.utils.pre_cache import pre_cache_service
except ImportError:  # pragma: no cover
    from routes import admin, data
    from utils.pre_cache import pre_cache_service

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover
    BackgroundScheduler = None

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(title="FloatChat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable) -> Response:
    started = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - started) * 1000, 2)
    logger.info("%s %s completed in %.2fms", request.method, request.url.path, duration_ms)
    response.headers["X-Process-Time-MS"] = str(duration_ms)
    return response


app.include_router(data.router)
app.include_router(admin.router)


@app.get("/")
def home() -> dict:
    return {
        "message": "🚀 FloatChat API is running!",
        "status": "ready",
        "endpoints": [
            "/api/data/region - POST (Fetch data by region)",
            "/api/data/float/{float_id} - GET (Fetch data by float ID)",
            "/api/data/search - GET (Search for floats in a region)",
            "/api/admin/cache/status - GET (Cache health)",
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "services": {"api": "running"}}


@app.get("/health/ready")
def ready() -> dict:
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> dict:
    return {
        "status": "ok",
        "cache": pre_cache_service.progress,
    }


@app.on_event("startup")
def startup_event() -> None:
    if BackgroundScheduler is not None:
        scheduler = BackgroundScheduler()
        scheduler.add_job(pre_cache_service.trigger, "cron", hour=3, minute=0)
        scheduler.start()
    pre_cache_service.start()


@app.on_event("shutdown")
def shutdown_event() -> None:
    pre_cache_service.stop()


if __name__ == "__main__":
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT, reload=settings.DEBUG)

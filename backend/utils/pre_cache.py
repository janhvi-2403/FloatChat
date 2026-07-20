import logging
import threading
from datetime import datetime
from typing import Any, Dict

from config import settings
try:
    from backend.utils.argo_fetcher import get_fetcher
except ImportError:  # pragma: no cover
    from utils.argo_fetcher import get_fetcher

logger = logging.getLogger(__name__)


class PreCacheService:
    """Background pre-caching service for popular regions."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread = None
        self.progress = {"status": "idle", "regions": [], "completed": 0, "failed": 0}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._precache_popular_regions()
            self._stop_event.wait(24 * 60 * 60)

    def _precache_popular_regions(self) -> None:
        fetcher = get_fetcher()
        self.progress = {"status": "running", "regions": [], "completed": 0, "failed": 0, "started_at": datetime.utcnow().isoformat()}
        for region in settings.PRE_CACHED_REGIONS:
            if self._stop_event.is_set():
                break
            try:
                self.progress["regions"].append(region)
                logger.info("Pre-caching region %s", region)
                fetcher.fetch_by_region(
                    lon_min=-180,
                    lon_max=180,
                    lat_min=-90,
                    lat_max=90,
                    time_start="2000-01-01",
                    time_end=datetime.utcnow().strftime("%Y-%m-%d"),
                    depth_min=0,
                    depth_max=2000,
                )
                self.progress["completed"] += 1
            except Exception as exc:
                logger.warning("Pre-cache failed for %s: %s", region, exc)
                self.progress["failed"] += 1
        self.progress["status"] = "completed"
        self.progress["finished_at"] = datetime.utcnow().isoformat()

    def trigger(self) -> Dict[str, Any]:
        self.start()
        return self.progress


pre_cache_service = PreCacheService()

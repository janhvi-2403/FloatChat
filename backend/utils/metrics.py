import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class MetricsCollector:
    """Collects application metrics for monitoring and health reporting."""

    alert_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "cache_hit_rate_min": 0.5,
            "response_time_ms_max": 5000.0,
            "storage_usage_percent_max": 90.0,
        }
    )
    metrics: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metrics.setdefault("cache_hits", 0)
        self.metrics.setdefault("cache_misses", 0)
        self.metrics.setdefault("gdac_calls", 0)
        self.metrics.setdefault("response_times_ms", [])
        self.metrics.setdefault("storage_usage_bytes", 0)

    def track_cache_hit(self) -> None:
        self.metrics["cache_hits"] += 1

    def track_cache_miss(self) -> None:
        self.metrics["cache_misses"] += 1

    def track_gdac_call(self) -> None:
        self.metrics["gdac_calls"] += 1

    def track_response_time(self, milliseconds: float) -> None:
        self.metrics["response_times_ms"].append(milliseconds)
        self.metrics["response_times_ms"] = self.metrics["response_times_ms"][-100:]

    def track_storage_usage(self, bytes_used: int) -> None:
        self.metrics["storage_usage_bytes"] = max(self.metrics["storage_usage_bytes"], bytes_used)

    def get_health_report(self) -> Dict[str, Any]:
        hits = self.metrics.get("cache_hits", 0)
        misses = self.metrics.get("cache_misses", 0)
        total = hits + misses
        hit_rate = round(hits / total, 4) if total else 0.0
        recent_times = self.metrics.get("response_times_ms", [])
        avg_response_ms = round(sum(recent_times) / len(recent_times), 2) if recent_times else 0.0
        alerts: List[str] = []
        if hit_rate < self.alert_thresholds.get("cache_hit_rate_min", 0.5):
            alerts.append("cache_hit_rate_low")
        if avg_response_ms > self.alert_thresholds.get("response_time_ms_max", 5000.0):
            alerts.append("response_time_high")
        return {
            "cache_hit_rate": hit_rate,
            "gdac_calls": self.metrics.get("gdac_calls", 0),
            "avg_response_ms": avg_response_ms,
            "storage_usage_bytes": self.metrics.get("storage_usage_bytes", 0),
            "alerts": alerts,
        }


metrics_collector = MetricsCollector()

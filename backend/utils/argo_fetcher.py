import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import xarray as xr

try:
    from argopy import ArgoIndex, DataFetcher
except ImportError:  # pragma: no cover
    ArgoIndex = None
    DataFetcher = None

try:
    from redis import Redis
except ImportError:  # pragma: no cover
    Redis = None

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import settings

try:
    from backend.utils.cache_manager import cache_manager
    from backend.utils.metrics import metrics_collector
    from backend.utils.rate_limiter import rate_limiter
except ImportError:  # pragma: no cover
    from utils.cache_manager import cache_manager
    from utils.metrics import metrics_collector
    from utils.rate_limiter import rate_limiter

try:
    from models.database import CachedRequest, get_session
except ImportError:  # pragma: no cover
    from backend.models.database import CachedRequest, get_session

# Set xarray to use scipy/h5netcdf backend for Windows compatibility
try:
    xr.set_options(file_cache_maxsize=100)
except AttributeError:
    pass

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


class ArgoDataFetcher:
    """Argo data fetcher with layered cache, rate limiting, metrics, and persistence."""

    def __init__(self, source: str = "gdac") -> None:
        self.source = source
        self.fetcher = DataFetcher(src=source) if DataFetcher else None
        self.cache_manager = cache_manager
        self.rate_limiter = rate_limiter
        self.metrics = metrics_collector
        self.last_cache_status = "miss"
        self.last_response_time_ms = 0.0
        logger.info("Initialized ArgoDataFetcher with source: %s", source)

    def _build_cache_key(self, prefix: str, **kwargs: Any) -> str:
        """Build a unique cache key from prefix and parameters."""
        payload = json.dumps({"prefix": prefix, **kwargs}, sort_keys=True)
        return f"argo:{prefix}:{payload}"

    def _persist_processed_result(
        self, 
        cache_key: str, 
        payload: Dict[str, Any], 
        query_type: str, 
        query_payload: Dict[str, Any]
    ) -> None:
        """Save processed result to PostgreSQL for persistence."""
        try:
            session = get_session()
            entry = CachedRequest(
                cache_key=cache_key,
                query_type=query_type,
                query_payload=query_payload,
                result_payload=payload,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=settings.CACHE_TTL_SECONDS),
            )
            session.add(entry)
            session.commit()
            session.close()
        except Exception as exc:
            logger.warning("Failed to persist processed result: %s", exc)

    def _db_get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result from PostgreSQL."""
        try:
            session = get_session()
            row = session.query(CachedRequest).filter(CachedRequest.cache_key == cache_key).first()
            session.close()
            if row and row.result_payload:
                return row.result_payload
        except Exception as exc:
            logger.warning("Database cache lookup failed: %s", exc)
        return None

    def _db_set(self, cache_key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        """Set cached result in PostgreSQL."""
        self._persist_processed_result(
            cache_key, 
            value, 
            "argo", 
            {"cache_key": cache_key, "ttl_seconds": ttl_seconds}
        )

    def fetch_by_region(
        self,
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float,
        time_start: str,
        time_end: str,
        depth_min: float = 0,
        depth_max: float = 2000,
    ) -> Dict[str, Any]:
        """
        Fetch Argo data for a specific region with multi-layer caching.
        
        Args:
            lon_min, lon_max: Longitude range (-180 to 180)
            lat_min, lat_max: Latitude range (-90 to 90)
            time_start: Start date (YYYY-MM-DD)
            time_end: End date (YYYY-MM-DD)
            depth_min, depth_max: Depth range in meters
            
        Returns:
            Dictionary with profile data
        """
        cache_key = self._build_cache_key(
            "region",
            lon_min=lon_min,
            lon_max=lon_max,
            lat_min=lat_min,
            lat_max=lat_max,
            time_start=time_start,
            time_end=time_end,
            depth_min=depth_min,
            depth_max=depth_max,
        )
        
        # Step 1: Check cache (Memory → Redis)
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            self.last_cache_status = "hit"
            self.metrics.track_cache_hit()
            logger.info("📦 Cache hit for region: %s", cache_key[:20])
            return cached

        # Step 2: Cache miss - fetch from GDAC
        self.last_cache_status = "miss"
        self.metrics.track_cache_miss()
        self.rate_limiter.acquire()
        self.metrics.track_gdac_call()
        started = time.perf_counter()
        
        try:
            if not self.fetcher:
                raise RuntimeError("argopy is not available")
            
            logger.info("🌐 Fetching fresh data from GDAC...")
            ds = (
                self.fetcher.region([
                    lon_min, lon_max, 
                    lat_min, lat_max, 
                    depth_min, depth_max, 
                    time_start, time_end
                ])
                .to_xarray()
            )
            
            # Convert to dictionary
            payload = self.dataset_to_dict(ds)
            
            # Store in all caches
            self.cache_manager.set(cache_key, payload)
            self._persist_processed_result(
                cache_key, 
                payload, 
                "region", {
                    "lon_min": lon_min,
                    "lon_max": lon_max,
                    "lat_min": lat_min,
                    "lat_max": lat_max,
                    "time_start": time_start,
                    "time_end": time_end,
                }
            )
            
            self.last_response_time_ms = round((time.perf_counter() - started) * 1000, 2)
            self.metrics.track_response_time(self.last_response_time_ms)
            
            logger.info("✅ Fetched %s profiles in %.2fms", 
                       payload['num_profiles'], self.last_response_time_ms)
            return payload
            
        except Exception as exc:
            logger.warning("GDAC region fetch failed; falling back to persistent cache: %s", exc)
            # Step 3: Fallback to PostgreSQL
            fallback = self._db_get(cache_key)
            if fallback is not None:
                self.cache_manager.set(cache_key, fallback)
                logger.info("📦 Restored from PostgreSQL fallback")
                return fallback
            raise

    def fetch_by_float(self, float_id: str) -> Dict[str, Any]:
        """
        Fetch data for a specific float by WMO ID.
        
        Args:
            float_id: WMO number of the float (e.g., '6903091')
            
        Returns:
            Dictionary with profile data
        """
        cache_key = self._build_cache_key("float", float_id=float_id)
        
        # Step 1: Check cache
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            self.last_cache_status = "hit"
            self.metrics.track_cache_hit()
            return cached

        # Step 2: Cache miss - fetch from GDAC
        self.last_cache_status = "miss"
        self.metrics.track_cache_miss()
        self.rate_limiter.acquire()
        self.metrics.track_gdac_call()
        started = time.perf_counter()
        
        try:
            if not self.fetcher:
                raise RuntimeError("argopy is not available")
            
            logger.info("🌐 Fetching data for float: %s", float_id)
            ds = self.fetcher.float(float_id).to_xarray()
            payload = self.dataset_to_dict(ds)
            
            # Store in caches
            self.cache_manager.set(cache_key, payload)
            self._persist_processed_result(
                cache_key, 
                payload, 
                "float", 
                {"float_id": float_id}
            )
            
            self.last_response_time_ms = round((time.perf_counter() - started) * 1000, 2)
            self.metrics.track_response_time(self.last_response_time_ms)
            
            logger.info("✅ Fetched %s profiles for float %s in %.2fms", 
                       payload['num_profiles'], float_id, self.last_response_time_ms)
            return payload
            
        except Exception as exc:
            logger.warning("GDAC float fetch failed; falling back to persistent cache: %s", exc)
            fallback = self._db_get(cache_key)
            if fallback is not None:
                self.cache_manager.set(cache_key, fallback)
                return fallback
            raise

    def search_floats(
        self,
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float,
        time_start: str,
        time_end: str,
    ) -> pd.DataFrame:
        """
        Search for floats in a region without fetching full profiles.
        
        Returns:
            DataFrame with float metadata
        """
        cache_key = self._build_cache_key(
            "search",
            lon_min=lon_min,
            lon_max=lon_max,
            lat_min=lat_min,
            lat_max=lat_max,
            time_start=time_start,
            time_end=time_end,
        )
        
        # Step 1: Check cache
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            self.last_cache_status = "hit"
            self.metrics.track_cache_hit()
            return pd.DataFrame(cached)

        # Step 2: Cache miss - search GDAC index
        self.last_cache_status = "miss"
        self.metrics.track_cache_miss()
        self.rate_limiter.acquire()
        self.metrics.track_gdac_call()
        
        try:
            if ArgoIndex is None:
                raise RuntimeError("argopy ArgoIndex is not available")
            
            logger.info("🔍 Searching for floats in region...")
            index = ArgoIndex()
            results = index.search(
                lon=[lon_min, lon_max], 
                lat=[lat_min, lat_max], 
                time=[time_start, time_end]
            )
            df = results.to_dataframe()
            
            # Store in cache
            self.cache_manager.set(cache_key, df.to_dict(orient="records"))
            logger.info("✅ Found %s floats in the region", len(df))
            return df
            
        except Exception as exc:
            logger.error("GDAC search failed: %s", exc)
            raise

    def dataset_to_dict(self, ds: xr.Dataset) -> Dict[str, Any]:
        """
        Convert xarray Dataset to a JSON-serializable dictionary.
        
        Args:
            ds: xarray.Dataset from argopy
            
        Returns:
            Dictionary with structured data
        """
        data = {
            "num_profiles": int(len(ds.N_PROF)) if "N_PROF" in ds.dims else 0,
            "floats": [],
            "metadata": {},
            "profiles": [],
        }
        
        # Extract float IDs
        float_ids = ds.FLOAT_SERIAL_NO.values if "FLOAT_SERIAL_NO" in ds else []
        data["floats"] = [str(f) for f in float_ids] if len(float_ids) > 0 else []
        
        # Extract profiles (limit to 100 for API response)
        profiles = []
        n_profiles = data["num_profiles"]
        limit = min(n_profiles, 100)
        
        for i in range(limit):
            try:
                profile = {
                    "profile_index": i,
                    "float_id": str(ds.FLOAT_SERIAL_NO[i].values) if "FLOAT_SERIAL_NO" in ds else "Unknown",
                    "latitude": float(ds.LATITUDE[i].values) if "LATITUDE" in ds else None,
                    "longitude": float(ds.LONGITUDE[i].values) if "LONGITUDE" in ds else None,
                    "date": str(ds.JULD[i].values) if "JULD" in ds else None,
                }
                
                # Add data arrays
                if "TEMP" in ds:
                    profile["temperature"] = ds.TEMP[i].values.tolist()
                if "PSAL" in ds:
                    profile["salinity"] = ds.PSAL[i].values.tolist()
                if "PRES" in ds:
                    profile["pressure"] = ds.PRES[i].values.tolist()
                
                profiles.append(profile)
            except Exception as exc:
                logger.warning("Could not extract profile %s: %s", i, exc)
                continue
        
        data["profiles"] = profiles
        data["metadata"] = {
            "source": self.source,
            "total_profiles": data["num_profiles"],
            "profiles_returned": len(profiles),
        }
        
        return data

    def save_to_netcdf(
        self, 
        ds: xr.Dataset, 
        filename: str, 
        directory: str = "data"
    ) -> str:
        """
        Save dataset to NetCDF file for caching.
        
        Args:
            ds: xarray.Dataset to save
            filename: Name of the file
            directory: Directory to save to
            
        Returns:
            Path to the saved file
        """
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, filename)
        
        try:
            # Try h5netcdf first (works on Windows)
            ds.to_netcdf(filepath, engine='h5netcdf')
        except Exception:
            try:
                # Fallback to scipy
                ds.to_netcdf(filepath, engine='scipy')
            except Exception:
                # Last resort - default engine
                ds.to_netcdf(filepath)
        
        logger.info("💾 Saved dataset to: %s", filepath)
        return filepath

    def get_cache_status(self) -> Dict[str, Any]:
        """Get current cache status."""
        return {
            "last_cache_status": self.last_cache_status,
            "last_response_time_ms": self.last_response_time_ms,
            "source": self.source
        }


# Singleton instance
_fetcher_instance: Optional[ArgoDataFetcher] = None


def get_fetcher(source: str = "gdac") -> ArgoDataFetcher:
    """
    Get or create a singleton ArgoDataFetcher instance.
    
    Args:
        source: 'gdac' (global) or 'incois' (regional)
        
    Returns:
        ArgoDataFetcher instance
    """
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = ArgoDataFetcher(source)
    return _fetcher_instance
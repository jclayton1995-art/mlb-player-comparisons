"""Cache manager for storing and retrieving data as parquet files."""

import os
from pathlib import Path
from typing import Optional
import pandas as pd


class CacheManager:
    """Manages caching of data to parquet files."""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe_key}.parquet"

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """Retrieve data from cache if it exists."""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                return pd.read_parquet(cache_path)
            except Exception:
                return None
        return None

    def set(self, key: str, data: pd.DataFrame) -> None:
        """Store data in cache."""
        if data is None or data.empty:
            return
        cache_path = self._get_cache_path(key)
        data.to_parquet(cache_path, index=False)

    def exists(self, key: str) -> bool:
        """Check if cache entry exists."""
        return self._get_cache_path(key).exists()

    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        for file in self.cache_dir.glob("*.parquet"):
            file.unlink()

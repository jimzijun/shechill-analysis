#!/usr/bin/env python3
"""
Plot Caching System for SheChill Web App
========================================

Provides multi-layer caching for plot generation to improve performance:
- File-based cache for generated plot images (persistent)
- In-memory cache for processed data (session-based)
- Smart cache invalidation based on forecast data timestamps
- Cache warmup and cleanup utilities
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


class PlotCache:
    """Manages multi-layer caching for plot generation"""

    def __init__(self, cache_dir: str = "data/plot_cache", max_memory_items: int = 50):
        """
        Initialize plot cache system

        Args:
            cache_dir: Directory for file-based plot cache
            max_memory_items: Maximum items in memory cache
        """
        self.cache_dir = Path(cache_dir)
        self.max_memory_items = max_memory_items

        # In-memory caches
        self._plot_cache: Dict[str, str] = {}  # plot_key -> base64_string
        self._data_cache: Dict[str, Any] = {}  # data_key -> processed_data
        self._access_times: Dict[str, datetime] = {}  # key -> last_access_time

        self.ensure_directories()

    def ensure_directories(self):
        """Create cache directory structure"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "plots").mkdir(exist_ok=True)
        (self.cache_dir / "metadata").mkdir(exist_ok=True)

    def get_cached_plot(
        self, item_name: str, plot_type: str, forecast_timestamp: str, historical_timestamp: str
    ) -> Optional[str]:
        """
        Get cached plot if available and valid

        Args:
            item_name: Name of the item
            plot_type: Type of plot ('grid' or 'simple')
            forecast_timestamp: Timestamp of forecast data
            historical_timestamp: Timestamp of historical data

        Returns:
            Base64 plot string or None if not cached/invalid
        """
        cache_key = self._generate_plot_key(item_name, plot_type, forecast_timestamp, historical_timestamp)

        # Check memory cache first
        if cache_key in self._plot_cache:
            self._access_times[cache_key] = datetime.now()
            return self._plot_cache[cache_key]

        # Check file cache
        cached_plot = self._load_plot_from_file(cache_key)
        if cached_plot:
            # Load into memory cache for faster next access
            self._store_in_memory(cache_key, cached_plot)
            return cached_plot

        return None

    def cache_plot(self, item_name: str, plot_type: str, forecast_timestamp: str, historical_timestamp: str, plot_base64: str):
        """
        Store plot in cache

        Args:
            item_name: Name of the item
            plot_type: Type of plot ('grid' or 'simple')
            forecast_timestamp: Timestamp of forecast data
            historical_timestamp: Timestamp of historical data
            plot_base64: Base64-encoded plot image
        """
        cache_key = self._generate_plot_key(item_name, plot_type, forecast_timestamp, historical_timestamp)

        # Store in memory cache
        self._store_in_memory(cache_key, plot_base64)

        # Store in file cache for persistence
        self._save_plot_to_file(
            cache_key,
            plot_base64,
            {
                "item_name": item_name,
                "plot_type": plot_type,
                "forecast_timestamp": forecast_timestamp,
                "historical_timestamp": historical_timestamp,
                "cached_at": datetime.now().isoformat(),
            },
        )

    def get_cached_data(self, data_key: str) -> Optional[Any]:
        """Get cached processed data"""
        if data_key in self._data_cache:
            self._access_times[data_key] = datetime.now()
            return self._data_cache[data_key]
        return None

    def cache_data(self, data_key: str, data: Any):
        """Store processed data in memory cache"""
        self._store_in_memory(data_key, data)

    def invalidate_item_cache(self, item_name: str):
        """Remove all cached data for a specific item"""
        # Remove from memory cache
        keys_to_remove = []
        for key in self._plot_cache.keys():
            if item_name.lower() in key.lower():
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self._plot_cache.pop(key, None)
            self._access_times.pop(key, None)

        # Remove from file cache
        for plot_file in (self.cache_dir / "plots").glob("*.png"):
            try:
                metadata_file = self.cache_dir / "metadata" / f"{plot_file.stem}.json"
                if metadata_file.exists():
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)
                    if metadata.get("item_name") == item_name:
                        plot_file.unlink(missing_ok=True)
                        metadata_file.unlink(missing_ok=True)
            except Exception as e:
                print(f"⚠️ Warning: Could not remove cache file {plot_file}: {e}")

    def cleanup_old_cache(self, max_age_days: int = 7):
        """Remove old cache files"""
        cutoff_time = datetime.now() - timedelta(days=max_age_days)

        # Clean file cache
        for metadata_file in (self.cache_dir / "metadata").glob("*.json"):
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)

                cached_at = datetime.fromisoformat(metadata.get("cached_at", "1970-01-01"))
                if cached_at < cutoff_time:
                    plot_file = self.cache_dir / "plots" / f"{metadata_file.stem}.png"
                    plot_file.unlink(missing_ok=True)
                    metadata_file.unlink(missing_ok=True)

            except Exception as e:
                print(f"⚠️ Warning: Could not clean cache file {metadata_file}: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        memory_plots = len(self._plot_cache)
        memory_data = len(self._data_cache)

        file_plots = len(list((self.cache_dir / "plots").glob("*.png")))

        total_size = 0
        if (self.cache_dir / "plots").exists():
            for plot_file in (self.cache_dir / "plots").glob("*.png"):
                total_size += plot_file.stat().st_size

        return {
            "memory_cache_plots": memory_plots,
            "memory_cache_data": memory_data,
            "file_cache_plots": file_plots,
            "file_cache_size_mb": round(total_size / 1024 / 1024, 2),
            "cache_dir": str(self.cache_dir),
        }

    def warmup_cache(self, forecast_manager, items_list: list):
        """Pre-generate cache for frequently accessed items"""
        from plot_renderer import render_item_plot

        print(f"🔥 Warming up plot cache for {len(items_list)} items...")

        # Load historical data once
        historical_data = self._load_historical_data()
        historical_timestamp = self._get_historical_timestamp()

        for i, item_info in enumerate(items_list):
            try:
                item_name = item_info["item_name"]

                # Load forecast data
                forecast_data = forecast_manager.load_item_forecast(item_name)
                if not forecast_data:
                    continue

                forecast_timestamp = forecast_data.get("metadata", {}).get("generated_at", "")
                quantity_data = historical_data.get(item_name, {})

                # Check if grid plot is already cached
                cached = self.get_cached_plot(item_name, "grid", forecast_timestamp, historical_timestamp)
                if not cached:
                    # Generate and cache grid plot
                    plot_base64 = render_item_plot(item_name, forecast_data, quantity_data, "grid")
                    if plot_base64:
                        self.cache_plot(item_name, "grid", forecast_timestamp, historical_timestamp, plot_base64)
                        print(f"✅ Cached grid plot for {item_name} ({i + 1}/{len(items_list)})")

            except Exception as e:
                print(f"❌ Error warming cache for {item_info.get('item_name', 'unknown')}: {e}")

    def _generate_plot_key(self, item_name: str, plot_type: str, forecast_ts: str, historical_ts: str) -> str:
        """Generate unique cache key for plot"""
        key_string = f"{item_name}:{plot_type}:{forecast_ts}:{historical_ts}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _store_in_memory(self, key: str, value: Any):
        """Store item in memory cache with LRU eviction"""
        # Remove oldest items if cache is full
        while len(self._plot_cache) >= self.max_memory_items:
            oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times.get(k, datetime.min))
            self._plot_cache.pop(oldest_key, None)
            self._data_cache.pop(oldest_key, None)
            self._access_times.pop(oldest_key, None)

        # Store new item
        if isinstance(value, str) and len(value) > 1000:  # Likely a base64 plot
            self._plot_cache[key] = value
        else:
            self._data_cache[key] = value

        self._access_times[key] = datetime.now()

    def _save_plot_to_file(self, cache_key: str, plot_base64: str, metadata: Dict[str, Any]):
        """Save plot to file cache"""
        try:
            import base64

            # Save plot image
            plot_file = self.cache_dir / "plots" / f"{cache_key}.png"
            plot_data = base64.b64decode(plot_base64)
            with open(plot_file, "wb") as f:
                f.write(plot_data)

            # Save metadata
            metadata_file = self.cache_dir / "metadata" / f"{cache_key}.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

        except Exception as e:
            print(f"⚠️ Warning: Could not save plot to file cache: {e}")

    def _load_plot_from_file(self, cache_key: str) -> Optional[str]:
        """Load plot from file cache"""
        try:
            import base64

            plot_file = self.cache_dir / "plots" / f"{cache_key}.png"
            metadata_file = self.cache_dir / "metadata" / f"{cache_key}.json"

            if not plot_file.exists() or not metadata_file.exists():
                return None

            # Check if cache is still valid (not older than 24 hours)
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            cached_at = datetime.fromisoformat(metadata.get("cached_at", "1970-01-01"))
            if datetime.now() - cached_at > timedelta(hours=24):
                return None

            # Load and encode plot
            with open(plot_file, "rb") as f:
                plot_data = f.read()

            return base64.b64encode(plot_data).decode("utf-8")

        except Exception as e:
            print(f"⚠️ Warning: Could not load plot from file cache: {e}")
            return None

    def _load_historical_data(self) -> Dict[str, Any]:
        """Load historical quantity data (cached helper)"""
        data_key = "historical_quantity_data"
        cached = self.get_cached_data(data_key)
        if cached:
            return cached

        # Load from CSV (same logic as app.py)
        try:
            from pathlib import Path

            project_root = Path(__file__).parent.parent
            csv_path = project_root / "data" / "quantity_per_day_per_item.csv"

            if not csv_path.exists():
                return {}

            df = pd.read_csv(csv_path)

            # Process data (simplified version of app.py logic)
            quantity_data = {}
            weekday_data: Dict[str, list] = {
                "Tuesday": [],
                "Wednesday": [],
                "Thursday": [],
                "Friday": [],
                "Saturday": [],
                "Sunday": [],
            }

            import re

            for idx, row in df.iterrows():
                date_formatted = row["Date"]
                match = re.match(r"(\d+/\d+) - (\w+)", date_formatted)
                if match:
                    date_str, weekday = match.groups()
                    if weekday in weekday_data:
                        weekday_data[weekday].append({"index": idx, "date_str": date_str, "date_formatted": date_formatted})

            item_columns = [col for col in df.columns if col != "Date"]
            for item_name in item_columns:
                item_data = {}
                for weekday, date_info_list in weekday_data.items():
                    dates, quantities, date_labels = [], [], []
                    for date_info in date_info_list:
                        idx = date_info["index"]
                        quantity = df.iloc[idx][item_name] if item_name in df.columns else 0
                        quantities.append(quantity)
                        dates.append(date_info["date_formatted"])
                        date_labels.append(date_info["date_str"])

                    item_data[weekday] = {"dates": dates, "quantities": quantities, "date_labels": date_labels}
                quantity_data[item_name] = item_data

            # Cache the processed data
            self.cache_data(data_key, quantity_data)
            return quantity_data

        except Exception as e:
            print(f"❌ Error loading historical data: {e}")
            return {}

    def _get_historical_timestamp(self) -> str:
        """Get timestamp of historical data file for cache invalidation"""
        try:
            from pathlib import Path

            project_root = Path(__file__).parent.parent
            csv_path = project_root / "data" / "quantity_per_day_per_item.csv"

            if csv_path.exists():
                mtime = csv_path.stat().st_mtime
                return datetime.fromtimestamp(mtime).isoformat()
        except Exception:
            pass
        return datetime.now().isoformat()


# Global instance
plot_cache = PlotCache()


def get_plot_cache() -> PlotCache:
    """Get the global plot cache instance"""
    return plot_cache


if __name__ == "__main__":
    # Test plot cache
    print("Plot Cache Test")
    print("=" * 40)

    cache = PlotCache()

    # Test data
    test_plot = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    # Test cache operations
    cache.cache_plot("Test Item", "grid", "2025-01-01T00:00:00", "2025-01-01T00:00:00", test_plot)

    cached = cache.get_cached_plot("Test Item", "grid", "2025-01-01T00:00:00", "2025-01-01T00:00:00")
    print(f"Cache test successful: {cached == test_plot}")

    stats = cache.get_cache_stats()
    print(f"Cache stats: {stats}")

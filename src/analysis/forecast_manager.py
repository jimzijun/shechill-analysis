#!/usr/bin/env python3
"""
Forecast Data Management for SheChill Analysis
==============================================

Handles saving and loading Prophet forecast data as JSON files.
Separates forecast computation from plot rendering for better architecture.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.logging_config import setup_logger


class ForecastManager:
    """Manages forecast data storage and retrieval"""

    def __init__(self, forecast_dir: str = "data/forecasts"):
        """Initialize forecast manager with storage directory"""
        self.forecast_dir = Path(forecast_dir)
        self.logger = setup_logger("ForecastManager")
        self.ensure_directories()

    def ensure_directories(self):
        """Create forecast directory structure if it doesn't exist"""
        self.forecast_dir.mkdir(parents=True, exist_ok=True)

    def save_item_forecast(self, item_name: str, forecast_data: Dict[str, Any]) -> bool:
        """
        Save forecast data for an item as JSON

        Args:
            item_name: Name of the item
            forecast_data: Dictionary containing forecast information

        Returns:
            bool: True if saved successfully
        """
        try:
            # Create safe filename
            safe_filename = self._sanitize_filename(item_name)
            filepath = self.forecast_dir / f"{safe_filename}_forecast.json"

            # Add metadata
            forecast_data["metadata"] = {
                "item_name": item_name,
                "generated_at": datetime.now().isoformat(),
                "format_version": "1.0",
            }

            # Convert numpy arrays to lists for JSON serialization
            json_data = self._serialize_forecast_data(forecast_data)

            with open(filepath, "w") as f:
                json.dump(json_data, f, indent=2)

            return True

        except Exception as e:
            self.logger.error(f"❌ Error saving forecast for {item_name}: {e}")
            return False

    def load_item_forecast(self, item_name: str) -> Optional[Dict[str, Any]]:
        """
        Load forecast data for an item

        Args:
            item_name: Name of the item

        Returns:
            Dict with forecast data or None if not found
        """
        try:
            safe_filename = self._sanitize_filename(item_name)
            filepath = self.forecast_dir / f"{safe_filename}_forecast.json"

            if not filepath.exists():
                return None

            with open(filepath, "r") as f:
                json_data = json.load(f)

            # Deserialize arrays back to numpy
            forecast_data = self._deserialize_forecast_data(json_data)

            return forecast_data

        except Exception as e:
            self.logger.error(f"❌ Error loading forecast for {item_name}: {e}")
            return None

    def get_available_forecasts(self) -> List[Dict[str, str]]:
        """
        Get list of available forecast files

        Returns:
            List of dicts with item info
        """
        forecasts: list[dict] = []

        if not self.forecast_dir.exists():
            return forecasts

        for filepath in self.forecast_dir.glob("*_forecast.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)

                metadata = data.get("metadata", {})
                forecasts.append(
                    {
                        "item_name": metadata.get("item_name", "Unknown"),
                        "filename": filepath.name,
                        "generated_at": metadata.get("generated_at", "Unknown"),
                        "file_path": str(filepath),
                    }
                )

            except Exception as e:
                self.logger.warning(f"⚠️  Warning: Could not read forecast file {filepath}: {e}")

        # Sort by item name
        forecasts.sort(key=lambda x: x["item_name"])
        return forecasts

    def delete_item_forecast(self, item_name: str) -> bool:
        """Delete forecast data for an item"""
        try:
            safe_filename = self._sanitize_filename(item_name)
            filepath = self.forecast_dir / f"{safe_filename}_forecast.json"

            if filepath.exists():
                filepath.unlink()
                return True
            return False

        except Exception as e:
            self.logger.error(f"❌ Error deleting forecast for {item_name}: {e}")
            return False

    def clear_all_forecasts(self) -> int:
        """Clear all forecast files from the forecast directory

        Returns:
            int: Number of forecast files deleted
        """
        deleted_count = 0

        try:
            if not self.forecast_dir.exists():
                self.logger.info("🔍 Forecast directory doesn't exist, nothing to clear")
                return 0

            # Find all forecast files
            forecast_files = list(self.forecast_dir.glob("*_forecast.json"))

            if not forecast_files:
                self.logger.info("🔍 No forecast files found to clear")
                return 0

            # Delete each forecast file
            for filepath in forecast_files:
                try:
                    filepath.unlink()
                    deleted_count += 1
                    self.logger.debug(f"🗑️  Deleted forecast file: {filepath.name}")
                except Exception as e:
                    self.logger.warning(f"⚠️  Failed to delete {filepath.name}: {e}")

            self.logger.info(f"🧹 Cleared {deleted_count} forecast files")
            return deleted_count

        except Exception as e:
            self.logger.error(f"❌ Error clearing all forecasts: {e}")
            return deleted_count

    def get_forecast_count(self) -> int:
        """Get the current number of forecast files

        Returns:
            int: Number of forecast files in the directory
        """
        try:
            if not self.forecast_dir.exists():
                return 0

            forecast_files = list(self.forecast_dir.glob("*_forecast.json"))
            return len(forecast_files)

        except Exception as e:
            self.logger.error(f"❌ Error counting forecasts: {e}")
            return 0

    def _sanitize_filename(self, item_name: str) -> str:
        """Convert item name to safe filename"""
        import re

        safe_name = re.sub(r"[^\w\s-]", "", item_name).replace(" ", "_")
        return safe_name.lower()

    def _serialize_forecast_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert numpy arrays to JSON-serializable format"""
        serialized: Dict[str, Any] = {}

        for key, value in data.items():
            if isinstance(value, np.ndarray):
                serialized[key] = value.tolist()
            elif isinstance(value, pd.DataFrame):
                # Convert DataFrame to dict format with timestamp handling
                records = []
                for _, row in value.iterrows():
                    record = {}
                    for col, val in row.items():
                        if isinstance(val, (pd.Timestamp, datetime)):
                            record[col] = val.isoformat()
                        else:
                            record[col] = val
                    records.append(record)

                serialized[key] = {
                    "data": records,
                    "columns": value.columns.tolist(),
                    "index": value.index.tolist(),
                }
            elif isinstance(value, pd.Series):
                serialized[key] = {
                    "data": value.tolist(),
                    "index": value.index.tolist(),
                    "name": value.name,
                }
            elif isinstance(value, (pd.Timestamp, datetime)):
                serialized[key] = value.isoformat()
            elif isinstance(value, dict):
                # Recursively serialize nested dicts
                serialized[key] = self._serialize_forecast_data(value)
            else:
                serialized[key] = value

        return serialized

    def _deserialize_forecast_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert JSON data back to numpy/pandas objects"""
        deserialized = {}

        for key, value in data.items():
            if isinstance(value, dict) and "data" in value and "columns" in value:
                # DataFrame format
                df = pd.DataFrame(value["data"])
                df.columns = value["columns"]
                if "index" in value:
                    df.index = value["index"]

                # Convert datetime columns back to datetime objects
                if "ds" in df.columns:
                    df["ds"] = pd.to_datetime(df["ds"])

                deserialized[key] = df
            elif isinstance(value, dict) and "data" in value and "index" in value and "name" in value:
                # Series format
                series = pd.Series(value["data"], index=value["index"], name=value["name"])
                deserialized[key] = series
            elif isinstance(value, list) and len(value) > 0:
                # Try to convert lists back to numpy arrays if they look numeric
                try:
                    if all(isinstance(x, (int, float)) for x in value):
                        deserialized[key] = np.array(value)
                    else:
                        deserialized[key] = value
                except Exception:
                    deserialized[key] = value
            elif isinstance(value, dict):
                # Recursively deserialize nested dicts
                deserialized[key] = self._deserialize_forecast_data(value)
            else:
                deserialized[key] = value

        return deserialized


# Global instance for easy access
forecast_manager = ForecastManager()


def get_forecast_manager() -> ForecastManager:
    """Get the global forecast manager instance"""
    return forecast_manager


if __name__ == "__main__":
    # Test forecast manager
    test_logger = setup_logger("ForecastManager-Test")
    test_logger.info("Forecast Manager Test")
    test_logger.info("=" * 40)

    mgr = ForecastManager()

    # Test data
    test_forecast = {
        "forecast_df": pd.DataFrame(
            {
                "ds": pd.date_range("2025-01-01", periods=10),
                "yhat": np.random.rand(10) * 100,
                "yhat_lower": np.random.rand(10) * 80,
                "yhat_upper": np.random.rand(10) * 120,
            }
        ),
        "historical_data": pd.Series([1, 2, 3, 4, 5], name="quantities"),
        "model_params": {"weekly_seasonality": True, "daily_seasonality": False},
    }

    # Test save/load
    item_name = "Test Croissant"
    test_logger.info(f"Testing save/load for: {item_name}")

    success = mgr.save_item_forecast(item_name, test_forecast)
    test_logger.info(f"Save successful: {success}")

    loaded = mgr.load_item_forecast(item_name)
    test_logger.info(f"Load successful: {loaded is not None}")

    if loaded:
        test_logger.info(f"Metadata: {loaded.get('metadata', {})}")

    # Show available forecasts
    available = mgr.get_available_forecasts()
    test_logger.info(f"Available forecasts: {len(available)}")

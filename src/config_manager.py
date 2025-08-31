#!/usr/bin/env python3
"""
Configuration Manager for SheChill Analysis App
==============================================

Centralized configuration loading and management for the application.
Handles loading from config/app_config.json with defaults and validation.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytz


class ConfigManager:
    """Manages application configuration loading and access"""

    def __init__(self, config_file: str = "config/app_config.json"):
        """Initialize config manager with config file path"""
        self.config_file = Path(config_file)
        self._config = None
        self._load_config()

    def _load_config(self):
        """Load configuration from file with defaults"""
        # Default configuration
        default_config = {
            "business": {
                "start_date": "2025-03-06",
                "timezone": "America/Los_Angeles",
                "name": "SheChill Patisserie",
            },
            "data_fetch": {"incremental_overlap_hours": 1},
        }

        # Load from file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    file_config = json.load(f)

                # Merge with defaults (file config takes precedence)
                self._config = self._deep_merge(default_config, file_config)

            except Exception as e:
                print(f"⚠️  Warning: Could not load config file {self.config_file}: {e}")
                print("   Using default configuration")
                self._config = default_config
        else:
            print(f"⚠️  Config file not found: {self.config_file}")
            print("   Using default configuration")
            self._config = default_config

    def _deep_merge(self, default: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries, with override taking precedence"""
        result = default.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    @property
    def business_start_date(self) -> datetime:
        """Get business start date as datetime object"""
        start_date_str = self._config["business"]["start_date"]
        return datetime.strptime(start_date_str, "%Y-%m-%d")

    @property
    def business_timezone(self) -> pytz.BaseTzInfo:
        """Get business timezone as pytz timezone object"""
        tz_str = self._config["business"]["timezone"]
        return pytz.timezone(tz_str)

    @property
    def business_name(self) -> str:
        """Get business name"""
        return self._config["business"]["name"]

    @property
    def incremental_overlap_hours(self) -> int:
        """Get incremental overlap hours for safety"""
        return self._config["data_fetch"]["incremental_overlap_hours"]

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value using dot notation (e.g., 'business.start_date')
        Returns default if key not found
        """
        keys = key_path.split(".")
        value = self._config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration dictionary"""
        return self._config.copy()

    def reload(self):
        """Reload configuration from file"""
        self._load_config()


# Global config instance for easy access
config = ConfigManager()


def get_config() -> ConfigManager:
    """Get the global configuration manager instance"""
    return config


if __name__ == "__main__":
    # Test configuration loading
    print("Configuration Manager Test")
    print("=" * 40)

    config_mgr = ConfigManager()

    print(f"Business Name: {config_mgr.business_name}")
    print(f"Start Date: {config_mgr.business_start_date}")
    print(f"Timezone: {config_mgr.business_timezone}")
    print(f"Overlap Hours: {config_mgr.incremental_overlap_hours}")

    print("\nFull config:")
    print(json.dumps(config_mgr.get_all(), indent=2, default=str))

#!/usr/bin/env python3
"""
Centralized Logging Configuration for SheChill Analysis
======================================================

Provides a single, consistent logging setup that all modules can use.
Eliminates duplicate logging configuration and ensures consistent formatting.

Usage:
    from src.logging_config import setup_logger

    # Daily rotating log file + console
    logger = setup_logger("MyModule", daily_file="my_module")

    # Fixed rotating log file + console
    logger = setup_logger("MyModule", log_file="my_module.log")

    # Console only
    logger = setup_logger("MyModule", console_only=True)
"""

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    daily_file: Optional[str] = None,
    console: bool = True,
    console_only: bool = False,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Set up a logger with consistent configuration.

    Args:
        name: Logger name (usually module name)
        log_file: Fixed log filename (uses RotatingFileHandler)
        daily_file: Base filename for daily logs (creates filename_YYYYMMDD.log)
        console: Whether to include console output (default: True)
        console_only: If True, only log to console (overrides file settings)
        level: Logging level (default: INFO)
        max_bytes: Max file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)

    Returns:
        Configured logger instance

    Examples:
        # Daily log files (existing pattern)
        logger = setup_logger("DataManager", daily_file="data_update")

        # Rotating log files (new pattern)
        logger = setup_logger("PlotCache", log_file="plot_cache.log")

        # Console only
        logger = setup_logger("WebApp", console_only=True)
    """

    # Get or create logger
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Consistent formatter for all handlers
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Console handler (consolidate logic to avoid duplication)
    if console or console_only:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Console only mode - exit early, no file handlers needed
    if console_only:
        return logger

    # File handlers
    if daily_file:
        # Daily rotating log file (existing pattern)
        today = datetime.now().strftime("%Y%m%d")
        log_path = log_dir / f"{daily_file}_{today}.log"
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    elif log_file:
        # Size-based rotating log file (new pattern)
        log_path = log_dir / log_file
        file_handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Convenience functions for common patterns
def setup_daily_logger(name: str, base_filename: str, console: bool = True, level: int = logging.INFO) -> logging.Logger:
    """Set up logger with daily rotating files (existing pattern)"""
    return setup_logger(name, daily_file=base_filename, console=console, level=level)


def setup_rotating_logger(name: str, filename: str, console: bool = True, level: int = logging.INFO) -> logging.Logger:
    """Set up logger with size-based rotating files (new pattern)"""
    return setup_logger(name, log_file=filename, console=console, level=level)


def setup_console_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up console-only logger"""
    return setup_logger(name, console_only=True, level=level)


if __name__ == "__main__":
    # Test the logging configuration
    test_logger = setup_console_logger("LoggingConfigTest")
    test_logger.info("Testing centralized logging configuration...")

    # Test different logger types
    daily_logger = setup_daily_logger("TestDaily", "test_daily")
    rotating_logger = setup_rotating_logger("TestRotating", "test_rotating.log")
    console_logger = setup_console_logger("TestConsole")

    # Test messages
    daily_logger.info("Daily logger test message")
    rotating_logger.info("Rotating logger test message")
    console_logger.info("Console logger test message")

    # Test levels
    daily_logger.debug("Debug message (should not appear)")
    daily_logger.warning("Warning message")
    daily_logger.error("Error message")

    test_logger.info("✅ Logging test completed. Check logs/ directory for output files.")
    test_logger.info("📁 Expected files: test_daily_YYYYMMDD.log, test_rotating.log")

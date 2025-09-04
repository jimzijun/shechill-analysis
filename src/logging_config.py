#!/usr/bin/env python3
"""
Centralized Logging Configuration for SheChill Analysis
======================================================

Provides a single, consistent console-only logging setup that all modules can use.

Usage:
    from src.logging_config import setup_logger

    # Console logging only
    logger = setup_logger("MyModule")
"""

import logging


def setup_logger(name: str) -> logging.Logger:
    """
    Set up a logger with console output only.

    Args:
        name: Logger name (usually module name)

    Returns:
        Configured logger instance
    """
    # Get or create logger
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Console handler with consistent formatting
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

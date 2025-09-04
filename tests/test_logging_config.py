#!/usr/bin/env python3
"""
Unit Tests for Centralized Logging Configuration
===============================================

Tests for src/logging_config.py to ensure proper console-only logger setup.
"""

import logging
import unittest

from src.logging_config import setup_logger


class TestLoggingConfig(unittest.TestCase):
    """Test cases for centralized logging configuration"""

    def setUp(self):
        """Set up test environment"""
        # Clear any existing loggers to ensure clean state
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if logger_name.startswith("Test"):
                logger = logging.getLogger(logger_name)
                logger.handlers.clear()
                logger.setLevel(logging.NOTSET)

    def test_setup_logger_creates_console_handler(self):
        """Test that setup_logger creates console-only logger"""
        logger = setup_logger("TestConsoleOnly")
        
        # Should have 1 handler: console only
        self.assertEqual(len(logger.handlers), 1)
        
        # Check handler type
        handler_types = [type(h).__name__ for h in logger.handlers]
        self.assertIn("StreamHandler", handler_types)
        
        # Verify log level
        self.assertEqual(logger.level, logging.INFO)

    def test_logger_no_duplicate_handlers(self):
        """Test that calling setup_logger twice doesn't create duplicate handlers"""
        logger1 = setup_logger("TestDuplicate")
        logger2 = setup_logger("TestDuplicate")
        
        # Should be the same logger instance
        self.assertIs(logger1, logger2)
        
        # Should not have duplicate handlers
        self.assertEqual(len(logger1.handlers), 1)

    def test_logger_formatter(self):
        """Test that logger uses correct formatter"""
        logger = setup_logger("TestFormatter")
        
        # Check that handlers have formatters
        for handler in logger.handlers:
            self.assertIsNotNone(handler.formatter)
            # Check formatter format string includes expected components
            format_str = handler.formatter._fmt
            self.assertIn("%(asctime)s", format_str)
            self.assertIn("%(name)s", format_str)
            self.assertIn("%(levelname)s", format_str)
            self.assertIn("%(message)s", format_str)

    def test_logger_level_default(self):
        """Test that logger defaults to INFO level"""
        logger1 = setup_logger("TestDefaultLevel")
        self.assertEqual(logger1.level, logging.INFO)


if __name__ == "__main__":
    unittest.main()
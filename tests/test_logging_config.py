#!/usr/bin/env python3
"""
Unit Tests for Centralized Logging Configuration
===============================================

Tests for src/logging_config.py to ensure proper logger setup and configuration.
"""

import logging
import tempfile
import unittest
from pathlib import Path

from src.logging_config import (
    setup_console_logger,
    setup_daily_logger,
    setup_logger,
    setup_rotating_logger,
)


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

    def test_setup_daily_logger_creates_correct_handlers(self):
        """Test that daily logger creates file and console handlers"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Patch the log directory to use temp directory
            import src.logging_config
            original_log_dir = src.logging_config.Path("logs")
            src.logging_config.Path = lambda x: Path(temp_dir) / x if x == "logs" else Path(x)
            
            try:
                logger = setup_daily_logger("TestDaily", "test_base")
                
                # Should have 2 handlers: file + console
                self.assertEqual(len(logger.handlers), 2)
                
                # Check handler types
                handler_types = [type(h).__name__ for h in logger.handlers]
                self.assertIn("FileHandler", handler_types)
                self.assertIn("StreamHandler", handler_types)
                
            finally:
                # Restore original Path
                src.logging_config.Path = original_log_dir.__class__

    def test_setup_rotating_logger_creates_correct_handlers(self):
        """Test that rotating logger creates rotating file and console handlers"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Patch the log directory
            import src.logging_config
            original_log_dir = src.logging_config.Path("logs")
            src.logging_config.Path = lambda x: Path(temp_dir) / x if x == "logs" else Path(x)
            
            try:
                logger = setup_rotating_logger("TestRotating", "test.log")
                
                # Should have 2 handlers: rotating file + console
                self.assertEqual(len(logger.handlers), 2)
                
                # Check handler types
                handler_types = [type(h).__name__ for h in logger.handlers]
                self.assertIn("RotatingFileHandler", handler_types)
                self.assertIn("StreamHandler", handler_types)
                
            finally:
                src.logging_config.Path = original_log_dir.__class__

    def test_setup_console_logger_only_console_handler(self):
        """Test that console logger only creates console handler"""
        logger = setup_console_logger("TestConsole")
        
        # Should have only 1 handler: console
        self.assertEqual(len(logger.handlers), 1)
        
        # Check handler type
        self.assertEqual(type(logger.handlers[0]).__name__, "StreamHandler")

    def test_prevents_duplicate_handlers(self):
        """Test that calling setup functions multiple times doesn't create duplicate handlers"""
        logger1 = setup_daily_logger("TestDuplicate", "test_base")
        logger2 = setup_daily_logger("TestDuplicate", "test_base")
        
        # Should be the same logger instance
        self.assertIs(logger1, logger2)
        
        # Should not have duplicate handlers
        self.assertEqual(len(logger1.handlers), 2)  # File + Console

    def test_console_only_mode_no_file_handler(self):
        """Test that console_only mode doesn't create file handlers"""
        with tempfile.TemporaryDirectory() as temp_dir:
            import src.logging_config
            original_log_dir = src.logging_config.Path("logs")
            src.logging_config.Path = lambda x: Path(temp_dir) / x if x == "logs" else Path(x)
            
            try:
                logger = setup_logger("TestConsoleOnly", daily_file="should_not_create", console_only=True)
                
                # Should have only console handler
                self.assertEqual(len(logger.handlers), 1)
                self.assertEqual(type(logger.handlers[0]).__name__, "StreamHandler")
                
                # Verify no log file was created
                log_files = list(Path(temp_dir).glob("*.log"))
                self.assertEqual(len(log_files), 0)
                
            finally:
                src.logging_config.Path = original_log_dir.__class__

    def test_no_console_handler_duplication(self):
        """Test that console handlers are not duplicated in different modes"""
        logger = setup_logger("TestNoDuplicate", console=True, console_only=False)
        
        # Should have only one console handler even with console=True
        console_handlers = [h for h in logger.handlers if type(h).__name__ == "StreamHandler"]
        self.assertEqual(len(console_handlers), 1)

    def test_formatter_consistency(self):
        """Test that all handlers use consistent formatting"""
        logger = setup_daily_logger("TestFormatter", "test_base")
        
        expected_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        for handler in logger.handlers:
            self.assertEqual(handler.formatter._fmt, expected_format)

    def test_log_level_setting(self):
        """Test that log level is set correctly"""
        logger = setup_logger("TestLevel", level=logging.WARNING)
        self.assertEqual(logger.level, logging.WARNING)
        
        # Default should be INFO
        logger2 = setup_console_logger("TestDefaultLevel")
        self.assertEqual(logger2.level, logging.INFO)

    def test_log_directory_creation(self):
        """Test that log directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            import src.logging_config
            log_path = Path(temp_dir) / "test_logs"
            
            # Monkey patch to use our test directory
            original_mkdir = Path.mkdir
            def mock_mkdir(self, **kwargs):
                if str(self).endswith("test_logs"):
                    log_path.mkdir(**kwargs)
                else:
                    original_mkdir(self, **kwargs)
            
            Path.mkdir = mock_mkdir
            src.logging_config.Path = lambda x: log_path if x == "logs" else Path(x)
            
            try:
                # This should create the directory
                setup_daily_logger("TestDirCreation", "test_base")
                
                # Verify directory was created
                self.assertTrue(log_path.exists())
                
            finally:
                Path.mkdir = original_mkdir
                src.logging_config.Path = Path

    def tearDown(self):
        """Clean up after each test"""
        # Clear test loggers
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if logger_name.startswith("Test"):
                logger = logging.getLogger(logger_name)
                logger.handlers.clear()


if __name__ == "__main__":
    unittest.main()
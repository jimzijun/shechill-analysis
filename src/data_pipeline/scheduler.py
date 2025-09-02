#!/usr/bin/env python3
"""
Automated Scheduling System for SheChill Analysis
=================================================

Provides automated scheduling for complete data pipeline operations:
- Daily full pipeline: fetch, process, and forecast generation at 10 PM
- Weekly full data integrity sync on Mondays at 6 AM
- Uses DataUpdateManager for unified pipeline coordination
- Background execution with proper logging

Usage:
    python scheduler.py --mode daily     # Test daily pipeline
    python scheduler.py --mode weekly    # Test weekly sync
    python scheduler.py --daemon         # Run as background daemon
"""

import argparse
import os
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.data_pipeline.data_update_manager import DataUpdateManager
from src.logging_config import PerformanceLogger, get_logger


class AutomationScheduler:
    """Handles automated scheduling of data pipeline operations"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.logger = get_logger(__name__, "AutomationScheduler")

        # Get Square access token
        self.access_token = os.getenv("SQUARE_ACCESS_TOKEN")
        if not self.access_token:
            self.logger.error("SQUARE_ACCESS_TOKEN not found in environment")
            raise ValueError("SQUARE_ACCESS_TOKEN required")

        # Initialize data update manager (no need for separate Square client)
        self.update_manager = DataUpdateManager(self.access_token, str(self.data_dir))

        # Initialize APScheduler
        self.scheduler = BlockingScheduler()

        self.logger.info("Automation scheduler initialized", extra={"data_dir": str(self.data_dir)})

    def daily_full_pipeline(self):
        """Run complete daily pipeline: fetch, process, and generate forecasts"""
        with PerformanceLogger(self.logger, "daily pipeline", operation="daily_pipeline"):
            try:
                # Run complete pipeline with incremental data fetch (7 days back for safety)
                result = self.update_manager.run_full_update_pipeline(days_back=7, force_full=False)

                if result["status"] == "success":
                    duration = result.get("duration_seconds", 0)
                    stages = result.get("stages", {})

                    # Log detailed results
                    self.logger.info(
                        "Daily pipeline completed successfully",
                        extra={
                            "operation": "daily_pipeline",
                            "duration_seconds": duration,
                            "stages": list(stages.keys()),
                            "stages_success": [k for k, v in stages.items() if v.get("status") == "success"],
                        },
                    )

                else:
                    self.logger.error(
                        "Daily pipeline failed",
                        extra={"operation": "daily_pipeline", "error": result.get("error", "Unknown error")},
                    )

            except Exception as e:
                self.logger.error(
                    "Daily pipeline error", extra={"operation": "daily_pipeline", "error": str(e)}, exc_info=True
                )

    def weekly_full_sync(self):
        """Perform full data synchronization weekly"""
        with PerformanceLogger(self.logger, "weekly sync", operation="weekly_sync"):
            try:
                # Run complete pipeline with full data refresh (30 days back)
                result = self.update_manager.run_full_update_pipeline(days_back=30, force_full=True)

                if result["status"] == "success":
                    duration = result.get("duration_seconds", 0)
                    self.logger.info(
                        "Weekly sync completed successfully",
                        extra={"operation": "weekly_sync", "duration_seconds": duration, "days_back": 30, "force_full": True},
                    )
                else:
                    self.logger.error(
                        "Weekly sync failed", extra={"operation": "weekly_sync", "error": result.get("error", "Unknown error")}
                    )

            except Exception as e:
                self.logger.error("Weekly sync error", extra={"operation": "weekly_sync", "error": str(e)}, exc_info=True)

    def setup_schedules(self):
        """Configure all scheduled tasks"""
        self.logger.info("Setting up schedules", extra={"operation": "schedule_setup"})

        # Daily full pipeline at 10 PM (after business hours)
        # This ensures we have complete daily sales data for forecasting
        self.scheduler.add_job(
            func=self.daily_full_pipeline,
            trigger=CronTrigger(hour=22, minute=0),  # 10:00 PM daily
            id="daily_pipeline",
            name="Daily Full Pipeline",
        )

        # Weekly full sync on Mondays at 6 AM for data integrity
        self.scheduler.add_job(
            func=self.weekly_full_sync,
            trigger=CronTrigger(day_of_week=0, hour=6, minute=0),  # Monday 6:00 AM
            id="weekly_sync",
            name="Weekly Full Sync",
        )

        self.logger.info(
            "Schedules configured successfully",
            extra={
                "operation": "schedule_setup",
                "daily_schedule": "22:00 (10 PM) daily",
                "weekly_schedule": "Monday 06:00 AM",
            },
        )

    def run_daemon(self):
        """Run scheduler as background daemon"""
        self.logger.info("Starting scheduler daemon", extra={"operation": "daemon_start"})
        self.setup_schedules()

        try:
            # Start the scheduler (this blocks until shutdown)
            self.scheduler.start()
        except KeyboardInterrupt:
            self.logger.info(
                "Keyboard interrupt received", extra={"operation": "daemon_shutdown", "reason": "keyboard_interrupt"}
            )
        except Exception as e:
            self.logger.error("Daemon error", extra={"operation": "daemon_error", "error": str(e)}, exc_info=True)
        finally:
            self.logger.info("Scheduler daemon stopped", extra={"operation": "daemon_stopped"})

    def shutdown(self, signum=None, frame=None):
        """Graceful shutdown handler"""
        # Parameters are required by signal handler but not used
        _ = signum, frame  # Suppress unused parameter warnings
        self.logger.info("📢 Shutdown signal received")
        if self.scheduler.running:
            self.scheduler.shutdown()

    def run_once(self, mode: str):
        """Run a single scheduled task for testing"""
        if mode == "daily":
            self.logger.info("Running single daily pipeline test", extra={"operation": "test", "mode": "daily"})
            self.daily_full_pipeline()
        elif mode == "weekly":
            self.logger.info("Running single weekly sync test", extra={"operation": "test", "mode": "weekly"})
            self.weekly_full_sync()
        else:
            self.logger.error(
                "Unknown mode", extra={"operation": "test", "mode": mode, "available_modes": ["daily", "weekly"]}
            )


def main():
    parser = argparse.ArgumentParser(description="SheChill Analysis Scheduler")
    parser.add_argument("--mode", choices=["daily", "weekly"], help="Run single operation for testing")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data)")

    args = parser.parse_args()

    try:
        scheduler = AutomationScheduler(args.data_dir)

        if args.mode:
            scheduler.run_once(args.mode)
        elif args.daemon:
            scheduler.run_daemon()
        else:
            print("Usage:")
            print("  python scheduler.py --mode [daily|weekly]  # Test single operation")
            print("  python scheduler.py --daemon               # Run background daemon")
            print("")
            print("Schedules:")
            print("  Daily:  10 PM - Full pipeline (fetch, process, forecast)")
            print("  Weekly: Monday 6 AM - Full data integrity sync")

    except Exception as e:
        print(f"❌ Scheduler failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

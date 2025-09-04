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
from src.logging_config import setup_logger


class AutomationScheduler:
    """Handles automated scheduling of data pipeline operations"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.setup_logging()

        # Get Square access token
        self.access_token = os.getenv("SQUARE_ACCESS_TOKEN")
        if not self.access_token:
            self.logger.error("SQUARE_ACCESS_TOKEN not found in environment")
            raise ValueError("SQUARE_ACCESS_TOKEN required")

        # Initialize data update manager (no need for separate Square client)
        self.update_manager = DataUpdateManager(self.access_token, str(self.data_dir))

        # Initialize APScheduler
        self.scheduler = BlockingScheduler()

        self.logger.info("Automation scheduler initialized")

    def setup_logging(self):
        """Setup logging for scheduler operations"""
        self.logger = setup_logger("AutomationScheduler")

    def daily_full_pipeline(self):
        """Run complete daily pipeline: fetch, process, and generate forecasts"""
        try:
            self.logger.info("📊 Starting daily full pipeline")

            # Run complete pipeline with incremental data fetch (7 days back for safety)
            result = self.update_manager.run_full_update_pipeline(days_back=7, force_full=False)

            if result["status"] == "success":
                duration = result.get("duration_seconds", 0)
                stages = result.get("stages", {})

                # Log detailed results
                self.logger.info(f"✅ Daily pipeline completed in {duration:.1f}s")
                for stage_name, stage_result in stages.items():
                    status_icon = "✅" if stage_result.get("status") == "success" else "❌"
                    self.logger.info(f"   {status_icon} {stage_name}: {stage_result.get('status', 'unknown')}")

            else:
                self.logger.error(f"❌ Daily pipeline failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.error(f"❌ Daily pipeline error: {e}")

    def weekly_full_sync(self):
        """Perform full data synchronization weekly"""
        try:
            self.logger.info("🔄 Starting weekly full sync")

            # Run complete pipeline with full data refresh (30 days back)
            result = self.update_manager.run_full_update_pipeline(days_back=30, force_full=True)

            if result["status"] == "success":
                duration = result.get("duration_seconds", 0)
                self.logger.info(f"✅ Weekly full sync completed in {duration:.1f}s")
            else:
                self.logger.error(f"❌ Weekly full sync failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.error(f"❌ Weekly full sync error: {e}")

    def setup_schedules(self):
        """Configure all scheduled tasks"""
        self.logger.info("⚙️ Setting up schedules...")

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

        self.logger.info("✅ Schedules configured:")
        self.logger.info("   - Daily pipeline: 10 PM daily (fetch, process, forecast)")
        self.logger.info("   - Full sync: Mondays 6 AM (data integrity check)")

    def run_daemon(self):
        """Run scheduler as background daemon"""
        self.logger.info("🚀 Starting scheduler daemon...")
        self.setup_schedules()

        try:
            # Start the scheduler (this blocks until shutdown)
            self.scheduler.start()
        except KeyboardInterrupt:
            self.logger.info("📢 Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"❌ Daemon error: {e}")
        finally:
            self.logger.info("🛑 Scheduler daemon stopped")

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
            self.logger.info("🧪 Running single daily pipeline")
            self.daily_full_pipeline()
        elif mode == "weekly":
            self.logger.info("🧪 Running single weekly sync")
            self.weekly_full_sync()
        else:
            self.logger.error(f"❌ Unknown mode: {mode}. Available modes: daily, weekly")


def main():
    parser = argparse.ArgumentParser(description="SheChill Analysis Scheduler")
    parser.add_argument("--mode", choices=["daily", "weekly"], help="Run single operation for testing")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data)")

    args = parser.parse_args()

    # Setup logging for CLI
    cli_logger = setup_logger("Scheduler-CLI")

    try:
        scheduler = AutomationScheduler(args.data_dir)

        if args.mode:
            scheduler.run_once(args.mode)
        elif args.daemon:
            scheduler.run_daemon()
        else:
            cli_logger.info("Usage:")
            cli_logger.info("  python scheduler.py --mode [daily|weekly]  # Test single operation")
            cli_logger.info("  python scheduler.py --daemon               # Run background daemon")
            cli_logger.info("")
            cli_logger.info("Schedules:")
            cli_logger.info("  Daily:  10 PM - Full pipeline (fetch, process, forecast)")
            cli_logger.info("  Weekly: Monday 6 AM - Full data integrity sync")

    except Exception as e:
        cli_logger.error(f"❌ Scheduler failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

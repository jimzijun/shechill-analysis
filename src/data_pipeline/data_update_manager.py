#!/usr/bin/env python3
"""
Data Update Manager for Live Forecasting Pipeline
================================================

Orchestrates the complete data update process:
1. Fetch new data from Square API
2. Process and clean the data
3. Update forecasting datasets
4. Trigger forecast regeneration
5. Update web dashboard

This manager coordinates all components of the live forecasting pipeline.
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, cast

from src.analysis import forecast_generator
from src.analysis.quantity_analysis import QuantityAnalyzer
from src.config_manager import get_config

# Import our components using proper src paths
from src.square_client.square_api_client import SquareAPIClient


class DataUpdateManager:
    """Orchestrates the complete live forecasting data update pipeline"""

    def __init__(self, access_token: str, data_dir: str = "data"):
        """Initialize the data update manager"""
        self.access_token = access_token
        self.data_dir = Path(data_dir)
        self.status_file = self.data_dir / "update_status.json"

        # Load configuration
        self.config = get_config()

        # Setup logging
        self._setup_logging()

        # Initialize Square API client
        self.square_client = SquareAPIClient(access_token, data_dir)

        self.logger.info("🔧 Data Update Manager initialized")

    def is_app_initialized(self) -> bool:
        """Check if the app has been initialized with data"""
        # Check for raw transactions data
        raw_data_dir = self.data_dir / "raw_transactions"
        if not raw_data_dir.exists():
            return False

        # Check if any transaction JSON files exist (excluding last_fetch.json)
        json_files = [f for f in raw_data_dir.glob("*.json") if f.name != "last_fetch.json"]
        if not json_files:
            return False

        # Check for last_fetch metadata
        last_fetch_file = raw_data_dir / "last_fetch.json"
        if not last_fetch_file.exists():
            return False

        return True

    def get_initialization_status(self) -> Dict[str, Any]:
        """Get detailed initialization status"""
        raw_data_dir = self.data_dir / "raw_transactions"

        status: Dict[str, Any] = {
            "is_initialized": self.is_app_initialized(),
            "raw_data_dir_exists": raw_data_dir.exists(),
            "transaction_files_count": 0,
            "has_last_fetch": False,
            "estimated_data_range": None,
        }

        if raw_data_dir.exists():
            json_files = [f for f in raw_data_dir.glob("*.json") if f.name != "last_fetch.json"]
            status["transaction_files_count"] = len(json_files)

            if json_files:
                # Get date range from filenames
                dates = []
                for file in json_files:
                    try:
                        date_str = file.stem  # filename without .json
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                        dates.append(date_obj)
                    except ValueError:
                        continue

                if dates:
                    dates.sort()
                    status["estimated_data_range"] = {
                        "start": dates[0].isoformat(),
                        "end": dates[-1].isoformat(),
                        "days": int((dates[-1] - dates[0]).days + 1),
                    }

            last_fetch_file = raw_data_dir / "last_fetch.json"
            status["has_last_fetch"] = last_fetch_file.exists()

        return status

    def _setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"update_manager_{datetime.now().strftime('%Y%m%d')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        )
        self.logger = logging.getLogger("DataUpdateManager")

    def get_update_status(self) -> Dict[str, Any]:
        """Get the current update status"""
        if not self.status_file.exists():
            return {
                "last_update_time": None,
                "status": "never_updated",
                "last_error": None,
                "pipeline_stages": {
                    "data_fetch": "pending",
                    "data_processing": "pending",
                    "forecast_generation": "pending",
                },
                "statistics": {
                    "total_transactions": 0,
                    "total_items": 0,
                    "data_coverage_days": 0,
                },
            }

        try:
            with open(self.status_file, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not read update status: {e}")
            return {"status": "error", "last_error": str(e)}

    def update_status(self, status_update: Dict[str, Any]):
        """Update the current status"""
        try:
            current_status = self.get_update_status()

            # Deep merge the status update
            if "pipeline_stages" in status_update:
                if "pipeline_stages" not in current_status:
                    current_status["pipeline_stages"] = {}
                current_status["pipeline_stages"].update(status_update["pipeline_stages"])
                del status_update["pipeline_stages"]

            if "statistics" in status_update:
                if "statistics" not in current_status:
                    current_status["statistics"] = {}
                current_status["statistics"].update(status_update["statistics"])
                del status_update["statistics"]

            # Update other fields
            current_status.update(status_update)

            with open(self.status_file, "w") as f:
                json.dump(current_status, f, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Failed to update status: {e}")

    def stage_data_fetch(self, days_back: int = 7, force_full: bool = False) -> Dict[str, Any]:
        """Stage 1: Fetch data from Square API"""
        self.logger.info("📥 STAGE 1: Fetching data from Square API")

        self.update_status(
            {
                "pipeline_stages": {"data_fetch": "running"},
                "current_stage": "data_fetch",
            }
        )

        try:
            result = self.square_client.perform_data_fetch(days_back, force_full)

            if result["status"] == "success":
                self.logger.info(f"✅ Data fetch completed: {result['orders_fetched']} orders")
                self.update_status(
                    {
                        "pipeline_stages": {"data_fetch": "completed"},
                        "statistics": {"orders_fetched": result["orders_fetched"]},
                    }
                )
                return {"status": "success", "data": result}
            else:
                self.logger.error(f"❌ Data fetch failed: {result.get('error', 'Unknown error')}")
                self.update_status(
                    {
                        "pipeline_stages": {"data_fetch": "failed"},
                        "last_error": result.get("error", "Data fetch failed"),
                    }
                )
                return {
                    "status": "error",
                    "error": result.get("error", "Data fetch failed"),
                }

        except Exception as e:
            error_msg = f"Data fetch stage failed: {e}"
            self.logger.error(f"❌ {error_msg}")
            self.update_status({"pipeline_stages": {"data_fetch": "failed"}, "last_error": error_msg})
            return {"status": "error", "error": error_msg}

    def stage_data_processing(self) -> Dict[str, Any]:
        """Stage 2: Process raw JSON data into analysis-ready format"""
        self.logger.info("🔄 STAGE 2: Processing raw data")

        self.update_status(
            {
                "pipeline_stages": {"data_processing": "running"},
                "current_stage": "data_processing",
            }
        )

        try:
            # Run the quantity analysis using the QuantityAnalyzer class
            self.logger.info("   Running quantity analysis...")

            # Create and run the analyzer
            analyzer = QuantityAnalyzer(str(self.data_dir))
            analyzer.run_analysis()

            # Check if the output file was created
            output_file = self.data_dir / "quantity_per_day_per_item.csv"
            if output_file.exists():
                self.logger.info("✅ Data processing completed successfully")

                # Get some statistics about the processed data
                stats = self._analyze_processed_data(output_file)

                self.update_status(
                    {
                        "pipeline_stages": {"data_processing": "completed"},
                        "statistics": stats,
                    }
                )

                return {
                    "status": "success",
                    "output_file": str(output_file),
                    "statistics": stats,
                }
            else:
                error_msg = "Data processing completed but output file not found"
                self.logger.error(f"❌ {error_msg}")
                self.update_status(
                    {
                        "pipeline_stages": {"data_processing": "failed"},
                        "last_error": error_msg,
                    }
                )
                return {"status": "error", "error": error_msg}

        except Exception as e:
            error_msg = f"Data processing stage failed: {e}"
            self.logger.error(f"❌ {error_msg}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")

            self.update_status(
                {
                    "pipeline_stages": {"data_processing": "failed"},
                    "last_error": error_msg,
                }
            )
            return {"status": "error", "error": error_msg}

    def _analyze_processed_data(self, output_file: Path) -> Dict[str, Any]:
        """Analyze the processed data to get statistics"""
        try:
            import pandas as pd

            # Read the processed data
            df = pd.read_csv(output_file)

            # CSV structure: Dates as rows, Items as columns
            # First column is 'Date', remaining columns are items

            # Count items (all columns except 'Date')
            item_columns = [col for col in df.columns if col != "Date"]
            total_items = len(item_columns)

            # Count data coverage days (number of date rows)
            data_coverage_days = len(df)

            # Calculate total transactions (sum of all quantity values)
            # Only sum the item columns, not the Date column
            total_transactions = df[item_columns].sum().sum()

            return {
                "total_items": int(total_items),
                "data_coverage_days": int(data_coverage_days),
                "total_transactions": int(total_transactions),
                "processed_data_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.warning(f"Could not analyze processed data: {e}")
            return {"total_items": 0, "data_coverage_days": 0, "total_transactions": 0}

    def stage_forecast_generation(self) -> Dict[str, Any]:
        """Stage 3: Generate new forecasting plots"""
        self.logger.info("📊 STAGE 3: Generating forecasting plots")

        self.update_status(
            {
                "pipeline_stages": {"forecast_generation": "running"},
                "current_stage": "forecast_generation",
            }
        )

        try:
            # Run the visualization generation
            self.logger.info("   Generating forecasting plots...")

            # Need to change to project root for forecast_generator to work correctly
            original_cwd = os.getcwd()
            try:
                os.chdir(self.data_dir.parent)  # Change to project root

                # Call the main function from forecast_generator
                forecast_generator.main()

            finally:
                os.chdir(original_cwd)

            # Check if forecast JSON files were generated
            forecasts_dir = self.data_dir / "forecasts"
            if forecasts_dir.exists() and list(forecasts_dir.glob("*_forecast.json")):
                forecast_count = len(list(forecasts_dir.glob("*_forecast.json")))
                self.logger.info(f"✅ Forecast generation completed: {forecast_count} forecast files generated")

                self.update_status(
                    {
                        "pipeline_stages": {"forecast_generation": "completed"},
                        "statistics": {"forecasts_generated": forecast_count},
                    }
                )

                return {"status": "success", "forecasts_generated": forecast_count}
            else:
                error_msg = "Forecast generation completed but no forecast files found"
                self.logger.error(f"❌ {error_msg}")
                self.update_status(
                    {
                        "pipeline_stages": {"forecast_generation": "failed"},
                        "last_error": error_msg,
                    }
                )
                return {"status": "error", "error": error_msg}

        except Exception as e:
            error_msg = f"Forecast generation stage failed: {e}"
            self.logger.error(f"❌ {error_msg}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")

            self.update_status(
                {
                    "pipeline_stages": {"forecast_generation": "failed"},
                    "last_error": error_msg,
                }
            )
            return {"status": "error", "error": error_msg}

    def run_full_update_pipeline(self, days_back: int = 7, force_full: bool = False) -> Dict[str, Any]:
        """Run the complete data update pipeline"""
        start_time = datetime.now()

        self.logger.info("🚀 STARTING FULL UPDATE PIPELINE")
        self.logger.info("=" * 60)

        self.update_status(
            {
                "status": "running",
                "pipeline_start_time": start_time.isoformat(),
                "last_error": None,
            }
        )

        pipeline_results = {}

        try:
            # Stage 1: Data Fetch
            result1 = self.stage_data_fetch(days_back, force_full)
            pipeline_results["data_fetch"] = result1

            if result1["status"] != "success":
                raise Exception(f"Data fetch failed: {result1['error']}")

            # Stage 2: Data Processing
            result2 = self.stage_data_processing()
            pipeline_results["data_processing"] = result2

            if result2["status"] != "success":
                raise Exception(f"Data processing failed: {result2['error']}")

            # Stage 3: Forecast Generation
            result3 = self.stage_forecast_generation()
            pipeline_results["forecast_generation"] = result3

            if result3["status"] != "success":
                raise Exception(f"Forecast generation failed: {result3['error']}")

            # Plots are now generated on-demand, no dashboard update needed

            # Success!
            duration = (datetime.now() - start_time).total_seconds()

            self.logger.info("=" * 60)
            self.logger.info(f"✅ PIPELINE COMPLETED SUCCESSFULLY in {duration:.1f}s")
            self.logger.info("=" * 60)

            self.update_status(
                {
                    "status": "success",
                    "last_update_time": datetime.now().isoformat(),
                    "pipeline_duration_seconds": duration,
                    "current_stage": "completed",
                }
            )

            return {
                "status": "success",
                "duration_seconds": duration,
                "stages": pipeline_results,
                "message": "Full update pipeline completed successfully",
            }

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)

            self.logger.error("=" * 60)
            self.logger.error(f"❌ PIPELINE FAILED after {duration:.1f}s")
            self.logger.error(f"Error: {error_msg}")
            self.logger.error("=" * 60)

            self.update_status(
                {
                    "status": "failed",
                    "last_update_time": datetime.now().isoformat(),
                    "last_error": error_msg,
                    "pipeline_duration_seconds": duration,
                }
            )

            return {
                "status": "failed",
                "error": error_msg,
                "duration_seconds": duration,
                "stages": pipeline_results,
            }

    def run_initialization(self) -> Dict[str, Any]:
        """Initialize the app with historical data from business start date"""
        start_time = datetime.now()

        self.logger.info("🚀 INITIALIZING APP - FIRST TIME SETUP")
        self.logger.info("=" * 70)

        # Check if already initialized
        if self.is_app_initialized():
            self.logger.warning("⚠️  App appears to already be initialized")
            init_status = self.get_initialization_status()
            self.logger.info(f"   Data range: {init_status['estimated_data_range']}")
            return {
                "status": "already_initialized",
                "message": "App is already initialized with data",
                "initialization_status": init_status,
            }

        self.logger.info(f"📅 Business start date: {self.config.business_start_date.date()}")
        self.logger.info(f"🏪 Business: {self.config.business_name}")

        self.update_status(
            {
                "status": "initializing",
                "initialization_start_time": start_time.isoformat(),
                "last_error": None,
            }
        )

        try:
            # Stage 1: Fetch all historical data from business start date
            self.logger.info("📥 STAGE 1: Fetching historical data from Square API")
            result = self.square_client.perform_data_fetch(days_back=0, force_full=True)

            if result["status"] != "success":
                raise Exception(f"Historical data fetch failed: {result.get('error', 'Unknown error')}")

            orders_fetched = result.get("orders_fetched", 0)
            self.logger.info(f"✅ Fetched {orders_fetched} historical orders")

            # Stage 2: Process the data
            self.logger.info("🔄 STAGE 2: Processing historical data")
            process_result = self.stage_data_processing()

            if process_result["status"] != "success":
                raise Exception(f"Data processing failed: {process_result.get('error', 'Unknown error')}")

            # Stage 3: Generate forecasting plots
            self.logger.info("📊 STAGE 3: Generating initial forecasting plots")
            forecast_result = self.stage_forecast_generation()

            if forecast_result["status"] != "success":
                raise Exception(f"Forecast generation failed: {forecast_result.get('error', 'Unknown error')}")

            # Plots are now generated on-demand, no dashboard update needed

            # Mark as initialized
            duration = (datetime.now() - start_time).total_seconds()

            self.logger.info("=" * 70)
            self.logger.info(f"✅ INITIALIZATION COMPLETED SUCCESSFULLY in {duration:.1f}s")
            self.logger.info("=" * 70)

            self.update_status(
                {
                    "status": "initialized",
                    "initialization_completed": datetime.now().isoformat(),
                    "initialization_duration_seconds": duration,
                    "historical_orders_fetched": orders_fetched,
                    "current_stage": "ready",
                }
            )

            # Get final status
            final_status = self.get_initialization_status()

            return {
                "status": "success",
                "duration_seconds": duration,
                "orders_fetched": orders_fetched,
                "data_range": final_status.get("estimated_data_range"),
                "message": "App successfully initialized with historical data",
            }

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)

            self.logger.error("=" * 70)
            self.logger.error(f"❌ INITIALIZATION FAILED after {duration:.1f}s")
            self.logger.error(f"Error: {error_msg}")
            self.logger.error("=" * 70)

            self.update_status(
                {
                    "status": "initialization_failed",
                    "last_error": error_msg,
                    "initialization_duration_seconds": duration,
                }
            )

            return {
                "status": "failed",
                "error": error_msg,
                "duration_seconds": duration,
            }

    def detect_system_state(self) -> Dict[str, Any]:
        """Detect current system state and determine what's needed to be ready"""
        self.logger.info("🔍 Detecting system state...")

        state: Dict[str, Any] = {
            "raw_data": self._check_raw_data_state(),
            "csv_data": self._check_csv_data_state(),
            "forecasts": self._check_forecast_state(),
            "system_ready": False,
            "required_actions": [],
        }

        # Determine required actions
        actions_needed = []

        if not state["raw_data"].get("has_recent_data", False):
            actions_needed.append("fetch_data")

        if not state["csv_data"].get("exists", False) or not state["csv_data"].get("up_to_date", False):
            actions_needed.append("run_analysis")

        if not state["forecasts"].get("exists", False) or not state["forecasts"].get("fresh", False):
            actions_needed.append("generate_forecasts")

        state["required_actions"] = actions_needed
        state["system_ready"] = len(actions_needed) == 0

        self.logger.info(f"📊 System state: {len(actions_needed)} actions needed")
        for action in actions_needed:
            self.logger.info(f"  → {action}")

        return state

    def _check_raw_data_state(self) -> Dict[str, Any]:
        """Check state of raw transaction data"""
        try:
            last_fetch_file = self.data_dir / "raw_transactions" / "last_fetch.json"

            if not last_fetch_file.exists():
                return {
                    "exists": False,
                    "has_recent_data": False,
                    "last_fetch": None,
                    "days_old": float("inf"),
                }

            with open(last_fetch_file, "r") as f:
                last_fetch = json.load(f)

            # Parse last fetch time
            last_fetch_time = datetime.fromisoformat(last_fetch.get("last_fetch_time", "1970-01-01"))
            days_old = (datetime.now() - last_fetch_time).days

            # Check for daily transaction files
            raw_dir = self.data_dir / "raw_transactions"
            daily_files = list(raw_dir.glob("2025-*.json"))

            return {
                "exists": True,
                "has_recent_data": days_old <= 1 and len(daily_files) > 0,
                "last_fetch": last_fetch_time.isoformat(),
                "days_old": days_old,
                "daily_files_count": len(daily_files),
            }

        except Exception as e:
            self.logger.warning(f"Error checking raw data state: {e}")
            return {"exists": False, "has_recent_data": False, "error": str(e)}

    def _check_csv_data_state(self) -> Dict[str, Any]:
        """Check state of processed CSV data"""
        try:
            csv_file = self.data_dir / "quantity_per_day_per_item.csv"

            if not csv_file.exists():
                return {
                    "exists": False,
                    "up_to_date": False,
                    "row_count": 0,
                    "date_range": None,
                }

            # Read CSV to check freshness
            import pandas as pd

            df = pd.read_csv(csv_file)

            # Extract date range from CSV
            dates = []
            for date_str in df["Date"].values:
                import re

                match = re.match(r"(\d+)/(\d+) - \w+", date_str)
                if match:
                    month, day = match.groups()
                    # Assume 2025 for current year
                    try:
                        date_obj = datetime(2025, int(month), int(day))
                        dates.append(date_obj)
                    except ValueError:
                        continue

            if dates:
                latest_csv_date = max(dates)
                days_old = (datetime.now() - latest_csv_date).days
                up_to_date = days_old <= 2  # Allow 2 days lag
            else:
                up_to_date = False
                latest_csv_date = None

            return {
                "exists": True,
                "up_to_date": up_to_date,
                "row_count": len(df),
                "date_range": {
                    "start": min(dates).isoformat() if dates else None,
                    "end": max(dates).isoformat() if dates else None,
                },
                "days_old": days_old if dates else float("inf"),
            }

        except Exception as e:
            self.logger.warning(f"Error checking CSV state: {e}")
            return {"exists": False, "up_to_date": False, "error": str(e)}

    def _check_forecast_state(self) -> Dict[str, Any]:
        """Check state of forecast data"""
        try:
            forecast_dir = self.data_dir / "forecasts"

            if not forecast_dir.exists():
                return {
                    "exists": False,
                    "fresh": False,
                    "count": 0,
                    "oldest_days": float("inf"),
                }

            forecast_files = list(forecast_dir.glob("*_forecast.json"))

            if not forecast_files:
                return {
                    "exists": False,
                    "fresh": False,
                    "count": 0,
                    "oldest_days": float("inf"),
                }

            # Check freshness of forecasts
            oldest_forecast = datetime.now()

            for forecast_file in forecast_files:
                try:
                    with open(forecast_file, "r") as f:
                        forecast_data = json.load(f)

                    generated_at = forecast_data.get("metadata", {}).get("generated_at")
                    if generated_at:
                        generated_time = datetime.fromisoformat(generated_at)
                        if generated_time < oldest_forecast:
                            oldest_forecast = generated_time

                except Exception:
                    continue

            days_old = (datetime.now() - oldest_forecast).days
            fresh = days_old <= 7  # Forecasts valid for 1 week

            return {
                "exists": True,
                "fresh": fresh,
                "count": len(forecast_files),
                "oldest_days": days_old,
            }

        except Exception as e:
            self.logger.warning(f"Error checking forecast state: {e}")
            return {"exists": False, "fresh": False, "error": str(e)}

    def bring_system_to_ready_state(self, access_token: Optional[str] = None) -> bool:
        """Automatically bring system to ready state by running required pipeline stages"""
        self.logger.info("🚀 Bringing system to ready state...")

        # Detect current state
        state = self.detect_system_state()

        if state["system_ready"]:
            self.logger.info("✅ System is already ready!")
            return True

        # Execute required actions in sequence
        success = True

        for action in state["required_actions"]:
            self.logger.info(f"🔄 Executing: {action}")

            if action == "fetch_data":
                if not access_token:
                    self.logger.warning("⚠️  Skipping data fetch - no access token provided")
                    continue

                if not self.square_client:
                    from src.square_client.square_api_client import SquareAPIClient

                    self.square_client = SquareAPIClient(access_token, str(self.data_dir))

                result = self.stage_data_fetch(days_back=7)
                if result["status"] != "success":
                    self.logger.error(f"❌ Data fetch failed: {result.get('error', 'Unknown error')}")
                    success = False
                    continue

            elif action == "run_analysis":
                result = self.stage_data_processing()
                if result["status"] != "success":
                    self.logger.error(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
                    success = False
                    continue

            elif action == "generate_forecasts":
                result = self.stage_forecast_generation()
                if result["status"] != "success":
                    self.logger.error(f"❌ Forecast generation failed: {result.get('error', 'Unknown error')}")
                    success = False
                    continue

        if success:
            self.logger.info("✅ System successfully brought to ready state!")
            return True
        else:
            self.logger.error("❌ Failed to bring system to ready state")
            return False

    def get_required_actions(self) -> list:
        """Get list of actions required to bring system to ready state"""
        state = self.detect_system_state()
        return state["required_actions"]


def main():
    """CLI interface for the data update manager"""
    import argparse

    parser = argparse.ArgumentParser(description="Data Update Manager for Live Forecasting")
    parser.add_argument("--days", type=int, default=7, help="Days to fetch (default: 7)")
    parser.add_argument("--full", action="store_true", help="Force full data refresh")
    parser.add_argument("--status", action="store_true", help="Show current status only")
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize app with historical data (first-time setup)",
    )
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data)")

    args = parser.parse_args()

    # Check for access token
    access_token = os.environ.get("SQUARE_ACCESS_TOKEN")
    if not access_token:
        print("❌ SQUARE_ACCESS_TOKEN not found in environment variables")
        print("   Set it with: export SQUARE_ACCESS_TOKEN='your_token_here'")
        sys.exit(1)

    print("=" * 70)
    print("DATA UPDATE MANAGER - LIVE FORECASTING PIPELINE")
    print("=" * 70)

    try:
        # Initialize manager
        manager = DataUpdateManager(access_token, args.data_dir)

        if args.status:
            # Show status and initialization info
            status = manager.get_update_status()
            init_status = manager.get_initialization_status()

            print(f"App Status: {status.get('status', 'unknown')}")
            print(f"Initialized: {init_status['is_initialized']}")
            print(f"Last Update: {status.get('last_update_time', 'never')}")

            if init_status["estimated_data_range"]:
                data_range = init_status["estimated_data_range"]
                print(f"Data Range: {data_range['start']} to {data_range['end']} ({data_range['days']} days)")

            if status.get("last_error"):
                print(f"Last Error: {status['last_error']}")

            stats = status.get("statistics", {})
            print(f"Total Items: {stats.get('total_items', 0)}")
            print(f"Total Transactions: {stats.get('total_transactions', 0)}")
            print(f"Data Coverage: {stats.get('data_coverage_days', 0)} days")

            # Exit with appropriate code based on status
            app_status = status.get("status", "unknown")
            if app_status in ["success", "initialized", "ready"]:
                sys.exit(0)  # Success
            elif app_status in ["failed", "error", "initialization_failed"]:
                sys.exit(1)  # Error
            else:
                sys.exit(2)  # Unknown/warning state

        elif args.init:
            # Initialize the app
            if manager.is_app_initialized():
                print("⚠️  App appears to already be initialized!")
                init_status = manager.get_initialization_status()
                if init_status["estimated_data_range"]:
                    data_range = init_status["estimated_data_range"]
                    print(f"   Existing data: {data_range['start']} to {data_range['end']} ({data_range['days']} days)")

                response = input("\nContinue with initialization anyway? This will fetch all historical data. (y/N): ")
                if response.lower() != "y":
                    print("Initialization cancelled.")
                    sys.exit(0)

            result = manager.run_initialization()

            print("\n" + "=" * 70)
            if result["status"] == "success":
                print("✅ INITIALIZATION SUCCESS!")
                print(f"⏱️  Duration: {result['duration_seconds']:.1f} seconds")
                print(f"📦 Orders fetched: {result.get('orders_fetched', 0)}")
                if result.get("data_range"):
                    data_range = result["data_range"]
                    print(f"📅 Data range: {data_range['start']} to {data_range['end']} ({data_range['days']} days)")
            elif result["status"] == "already_initialized":
                print("⚠️  ALREADY INITIALIZED")
                print(result["message"])
            else:
                print("❌ INITIALIZATION FAILED!")
                print(f"Error: {result['error']}")
                print(f"⏱️  Duration: {result['duration_seconds']:.1f} seconds")
            print("=" * 70)

        else:
            # Run the full pipeline
            result = manager.run_full_update_pipeline(args.days, args.full)

            print("\n" + "=" * 70)
            if result["status"] == "success":
                print("✅ PIPELINE SUCCESS!")
                print(f"⏱️  Duration: {result['duration_seconds']:.1f} seconds")

                # Show stage results
                stages = result.get("stages", {})
                for stage_name, stage_result in stages.items():
                    status_icon = "✅" if stage_result["status"] == "success" else "❌"
                    print(f"{status_icon} {stage_name}: {stage_result['status']}")

            else:
                print("❌ PIPELINE FAILED!")
                print(f"Error: {result['error']}")
                print(f"⏱️  Duration: {result['duration_seconds']:.1f} seconds")

            print("=" * 70)

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

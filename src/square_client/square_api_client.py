#!/usr/bin/env python3
"""
Enhanced Square API Client for Live Forecasting
==============================================

Robust Square API client for fetching transaction data with incremental updates,
error recovery, and proper data formatting for forecasting pipeline.

Features:
- Incremental data fetching (only fetch new transactions)
- Rate limiting and error recovery
- JSON-based data storage with daily file organization
- Comprehensive logging and monitoring
- Data validation and quality checks
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.config_manager import get_config
from src.logging_config import setup_daily_logger

try:
    from square import Square
    from square.environment import SquareEnvironment
except ImportError:
    from src.logging_config import setup_console_logger

    logger = setup_console_logger("SquareAPIClient")
    logger.error("❌ Square SDK not installed. Install with: pip install squareup")
    sys.exit(1)

try:
    from dotenv import load_dotenv

    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # dotenv not installed, continue without it


class SquareAPIClient:
    """Enhanced Square API client for live forecasting data"""

    def __init__(self, access_token: str, data_dir: str = "data"):
        """Initialize Square client with enhanced features"""
        self.access_token = access_token
        self.data_dir = Path(data_dir)
        self.raw_data_dir = self.data_dir / "raw_transactions"
        self.metadata_file = self.raw_data_dir / "last_fetch.json"

        # Load configuration
        self.config = get_config()
        self.business_timezone = self.config.business_timezone

        # Setup logging
        self._setup_logging()

        # Create directories
        self._ensure_directories()

        # Initialize Square client
        self.client = Square(token=access_token, environment=SquareEnvironment.PRODUCTION)

        # Get locations
        self.locations = self._get_locations()
        if not self.locations:
            raise ValueError("No locations found")

        # Find SheChill Patisserie location, fallback to first location
        self.location_id = self.locations[0]["id"]  # Default fallback
        self.location_name = self.locations[0]["name"]
        for loc in self.locations:
            if "shechill" in loc["name"].lower():
                self.location_id = loc["id"]
                self.location_name = loc["name"]
                break

        self.logger.info("✅ Connected to Square API")
        self.logger.info(f"📍 Using location: {self.location_name} ({self.location_id})")
        self.logger.info(f"💾 Data directory: {self.data_dir}")
        self.logger.info(f"🕐 Business timezone: {self.business_timezone}")
        self.logger.info(f"🏪 Business: {self.config.business_name}")
        self.logger.info(f"📅 Business start date: {self.config.business_start_date.date()}")

    def _setup_logging(self):
        """Setup logging configuration"""
        self.logger = setup_daily_logger("SquareAPIClient", "square_api")

    def _ensure_directories(self):
        """Create necessary directories"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(parents=True, exist_ok=True)

    def _get_locations(self) -> List[Dict[str, Any]]:
        """Get all locations with error handling"""
        try:
            locations_response = self.client.locations.list()
            locations = getattr(locations_response, "locations", [])
            return [{"id": loc.id, "name": loc.name} for loc in locations]
        except Exception as e:
            self.logger.error(f"❌ Error getting locations: {e}")
            return []

    def get_last_fetch_info(self) -> Dict[str, Any]:
        """Get information about the last successful fetch"""
        if not self.metadata_file.exists():
            return {
                "last_fetch_time": None,
                "last_order_time": None,
                "total_transactions_fetched": 0,
                "last_fetch_status": "never",
            }

        try:
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not read last fetch info: {e}")
            return {
                "last_fetch_time": None,
                "last_order_time": None,
                "total_transactions_fetched": 0,
                "last_fetch_status": "error",
            }

    def update_last_fetch_info(self, info: Dict[str, Any]):
        """Update the last fetch metadata"""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(info, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to update last fetch info: {e}")

    def get_fetch_date_range(self, days_back: int = 7, force_full: bool = False) -> Tuple[datetime, datetime]:
        """Calculate optimal date range for fetching data"""
        end_date = datetime.now(timezone.utc)

        if force_full:
            # Full fetch: get all data from business start date
            business_start = self.config.business_start_date
            start_date = business_start.replace(tzinfo=timezone.utc)
            self.logger.info(f"📅 Full data fetch from business start: {business_start.date()}")
        else:
            # Incremental fetch: get data since last successful fetch
            last_fetch = self.get_last_fetch_info()
            if last_fetch.get("last_order_time") or last_fetch.get("last_transaction_time"):
                # Start from last successful fetch with configurable overlap for safety
                # Handle both old and new field names for backward compatibility
                time_field = last_fetch.get("last_order_time") or last_fetch.get("last_transaction_time")
                last_time = datetime.fromisoformat(time_field.replace("Z", "+00:00"))
                overlap_hours = self.config.incremental_overlap_hours
                start_date = last_time - timedelta(hours=overlap_hours)
                self.logger.info(f"📅 Incremental fetch from {start_date}")
            else:
                # First fetch: get recent data
                start_date = end_date - timedelta(days=days_back)
                self.logger.info(f"📅 Initial fetch: {days_back} days of data")

        return start_date, end_date

    def fetch_transactions(
        self,
        start_date: datetime,
        end_date: datetime,
        max_retries: int = 3,
        rate_limit_delay: float = 1.0,
    ) -> Dict[str, List[Dict]]:
        """
        Fetch transactions with proper error handling and rate limiting
        Returns: {date_string: [transactions]}
        """
        self.logger.info(f"📥 Fetching transactions from {start_date} to {end_date}")

        transactions_by_date: dict[str, list] = {}
        cursor = None
        page = 1
        total_orders = 0
        retry_count = 0

        while True:
            try:
                self.logger.info(f"   📄 Fetching page {page}...")

                # Rate limiting
                if page > 1:
                    time.sleep(rate_limit_delay)

                # Prepare search request
                query_params: Dict[str, Any] = {
                    "filter": {
                        "date_time_filter": {
                            "created_at": {
                                "start_at": start_date.isoformat().replace("+00:00", "Z"),
                                "end_at": end_date.isoformat().replace("+00:00", "Z"),
                            }
                        },
                        "state_filter": {
                            "states": [
                                "COMPLETED",
                                "OPEN",
                            ]  # Only get completed/open orders
                        },
                    }
                }

                result = self.client.orders.search(
                    location_ids=[self.location_id],
                    query=query_params,  # type: ignore[arg-type]
                    limit=100,
                    cursor=cursor,
                )

                # Process the response
                orders = getattr(result, "orders", []) or []
                total_orders += len(orders)

                # Save raw orders directly instead of processing into line items
                for order in orders:
                    # Get the raw order data
                    if hasattr(order, "model_dump"):
                        # For Pydantic models, use model_dump to get clean dict
                        raw_order_data = order.model_dump()
                    elif hasattr(order, "__dict__"):
                        # For regular objects, use __dict__
                        raw_order_data = order.__dict__
                    else:
                        # Fallback: convert to dict representation
                        raw_order_data = {attr: getattr(order, attr) for attr in dir(order) if not attr.startswith("_")}

                    # Extract date for organization
                    created_at = raw_order_data.get("created_at")
                    if created_at:
                        # Parse date and convert to business timezone
                        order_datetime_utc = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        order_datetime_local = order_datetime_utc.astimezone(self.business_timezone)
                        date_str = order_datetime_local.strftime("%Y-%m-%d")

                        if date_str not in transactions_by_date:
                            transactions_by_date[date_str] = []

                        # Add timestamp in business timezone to the raw data
                        raw_order_data["local_datetime"] = order_datetime_local.isoformat()
                        raw_order_data["date"] = date_str

                        transactions_by_date[date_str].append(raw_order_data)

                # Check for more pages
                cursor = getattr(result, "cursor", None)
                if not cursor:
                    break

                page += 1
                retry_count = 0  # Reset retry count on successful request

            except Exception as e:
                retry_count += 1
                self.logger.error(f"❌ Error on page {page}, attempt {retry_count}: {e}")

                if retry_count >= max_retries:
                    self.logger.error(f"❌ Max retries ({max_retries}) reached, stopping fetch")
                    break

                # Exponential backoff
                wait_time = rate_limit_delay * (2**retry_count)
                self.logger.info(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        self.logger.info(f"✅ Fetched {total_orders} raw orders into {len(transactions_by_date)} date groups")
        return transactions_by_date

    def save_daily_orders(self, orders_by_date: Dict[str, List[Dict]]) -> int:
        """
        Save raw Square orders organized by date to daily JSON files
        Returns number of order records saved
        """
        total_saved = 0

        for date_str, orders in orders_by_date.items():
            if not orders:
                continue

            # Save to raw_transactions directory (same as before but with raw orders)
            file_path = self.raw_data_dir / f"{date_str}.json"

            # Load existing data if file exists
            existing_data = []
            if file_path.exists():
                try:
                    with open(file_path, "r") as f:
                        existing_data = json.load(f)
                except Exception as e:
                    self.logger.warning(f"Could not load existing data for {date_str}: {e}")

            # Merge with new orders (avoid duplicates by order ID)
            existing_ids = {order.get("id", "") for order in existing_data}
            new_orders = []

            for order in orders:
                order_id = order.get("id", "")
                if order_id and order_id not in existing_ids:
                    new_orders.append(order)

            if new_orders:
                all_orders = existing_data + new_orders
                # Sort by created_at timestamp
                all_orders.sort(key=lambda x: x.get("created_at", ""))

                # Save to file
                try:
                    with open(file_path, "w") as f:
                        json.dump(all_orders, f, indent=2, default=str)

                    self.logger.info(f"💾 Saved {len(new_orders)} new raw orders for {date_str}")
                    total_saved += len(new_orders)

                except Exception as e:
                    self.logger.error(f"❌ Failed to save raw orders for {date_str}: {e}")
            else:
                self.logger.info(f"   No new orders for {date_str}")

        return total_saved

    def perform_data_fetch(self, days_back: int = 7, force_full: bool = False) -> Dict[str, Any]:
        """
        Perform complete data fetch operation with metadata tracking
        Returns summary of the fetch operation
        """
        start_time = datetime.now()
        self.logger.info("🚀 Starting data fetch operation")

        try:
            # Calculate date range
            start_date, end_date = self.get_fetch_date_range(days_back, force_full)

            # Fetch raw orders
            orders_by_date = self.fetch_transactions(start_date, end_date)

            if not orders_by_date:
                self.logger.warning("⚠️  No orders found in date range")
                return {
                    "status": "success",
                    "orders_fetched": 0,
                    "date_range": [start_date.isoformat(), end_date.isoformat()],
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                }

            # Save raw orders
            total_saved = self.save_daily_orders(orders_by_date)

            # Calculate latest order time for next incremental fetch
            latest_order_time = None
            for orders in orders_by_date.values():
                for order in orders:
                    order_time = order.get("created_at")
                    if order_time and (not latest_order_time or order_time > latest_order_time):
                        latest_order_time = order_time

            # Update metadata
            fetch_info = {
                "last_fetch_time": datetime.now().isoformat(),
                "last_order_time": latest_order_time,
                "total_orders_fetched": total_saved,
                "last_fetch_status": "success",
                "date_range_start": start_date.isoformat(),
                "date_range_end": end_date.isoformat(),
            }
            self.update_last_fetch_info(fetch_info)

            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"✅ Data fetch completed successfully in {duration:.1f}s")
            self.logger.info(f"📊 Fetched {total_saved} new raw orders")

            return {
                "status": "success",
                "orders_fetched": total_saved,
                "date_range": [start_date.isoformat(), end_date.isoformat()],
                "duration_seconds": duration,
                "latest_order_time": latest_order_time,
            }

        except Exception as e:
            self.logger.error(f"❌ Data fetch failed: {e}")

            # Update metadata with error status
            fetch_info = {
                "last_fetch_time": datetime.now().isoformat(),
                "last_fetch_status": "error",
                "last_error": str(e),
            }
            self.update_last_fetch_info(fetch_info)

            return {
                "status": "error",
                "error": str(e),
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }


def main():
    """CLI interface for testing the API client"""
    import argparse

    parser = argparse.ArgumentParser(description="Square API Client for Live Forecasting")
    parser.add_argument("--days", type=int, default=7, help="Days to fetch (default: 7)")
    parser.add_argument("--full", action="store_true", help="Force full data fetch")
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data)")

    args = parser.parse_args()

    # Setup logging for CLI
    from src.logging_config import setup_console_logger

    cli_logger = setup_console_logger("SquareAPIClient-CLI")

    # Check for access token
    access_token = os.environ.get("SQUARE_ACCESS_TOKEN")
    if not access_token:
        cli_logger.error("❌ SQUARE_ACCESS_TOKEN not found in environment variables")
        cli_logger.info("   Set it with: export SQUARE_ACCESS_TOKEN='your_token_here'")
        sys.exit(1)

    cli_logger.info("=" * 60)
    cli_logger.info("SQUARE API CLIENT - LIVE FORECASTING")
    cli_logger.info("=" * 60)

    try:
        # Initialize client
        client = SquareAPIClient(access_token, args.data_dir)

        # Perform data fetch
        result = client.perform_data_fetch(args.days, args.full)

        # Print results
        cli_logger.info("\n" + "=" * 60)
        if result["status"] == "success":
            cli_logger.info("✅ SUCCESS!")
            cli_logger.info(f"📊 Raw orders fetched: {result.get('orders_fetched', 0)}")
            cli_logger.info(f"⏱️  Duration: {result['duration_seconds']:.1f} seconds")
        else:
            cli_logger.error("❌ FAILED!")
            cli_logger.error(f"Error: {result['error']}")
        cli_logger.info("=" * 60)

    except Exception as e:
        cli_logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

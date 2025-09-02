"""
Shechill Patisserie Forecast Generator Script
=============================================

This script generates Prophet forecast data from the quantity analysis data
to support dynamic plot rendering and inventory planning decisions.

Directory Structure:
- /data/quantity_per_day_per_item.csv - Input data from quantity analysis
- /data/forecasts/ - JSON forecast data per item

Output Data:
- JSON files: Forecast data with historical context for each item
"""

import os
import re
import warnings

import numpy as np
import pandas as pd
from prophet import Prophet

from src.analysis.forecast_manager import get_forecast_manager
from src.logging_config import PerformanceLogger, get_logger

warnings.filterwarnings("ignore", category=FutureWarning)


def ensure_directories(logger=None):
    """Create forecast data directory structure if it doesn't exist"""
    directories = ["data/forecasts"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    if logger:
        logger.debug("Created forecast directories", extra={"directories": directories})
    else:
        print(f"Created {len(directories)} forecast directories")


def load_quantity_data(logger=None):
    """Load and parse the quantity per day per item data"""
    if logger:
        logger.info("Loading quantity data")
    else:
        print("Loading quantity data...")

    df = pd.read_csv("data/quantity_per_day_per_item.csv")

    if logger:
        logger.info(
            "Loaded quantity data", extra={"data_shape": df.shape, "unique_dates": len(df), "item_columns": df.shape[1] - 1}
        )
    else:
        print(f"Loaded data shape: {df.shape}")
        print(f"Dates: {len(df)} unique dates")
        print(f"Item columns: {df.shape[1] - 1} items (excluding Date)")

    return df


def parse_date_rows(df):
    """Parse date rows and extract weekday/date information"""
    print("Parsing date rows...")

    date_info = []
    weekday_data = {
        "Tuesday": [],
        "Wednesday": [],
        "Thursday": [],
        "Friday": [],
        "Saturday": [],
        "Sunday": [],
    }

    # Parse each date row from Date column
    for idx, row in df.iterrows():
        date_formatted = row["Date"]
        # Parse format: "M/D - DayName"
        match = re.match(r"(\d+)/(\d+) - (\w+)", date_formatted)
        if match:
            month, day, weekday = match.groups()
            date_info.append(
                {
                    "index": idx,
                    "date_formatted": date_formatted,
                    "month": int(month),
                    "day": int(day),
                    "weekday": weekday,
                    "date_value": date_formatted,
                }
            )
            if weekday in weekday_data:
                weekday_data[weekday].append(idx)

    print(f"Parsed {len(date_info)} date rows")
    for weekday, indices in weekday_data.items():
        print(f"  {weekday}: {len(indices)} dates")

    return date_info, weekday_data


def create_full_timeseries_forecast(df, item_name, forecast_days=28):
    """Create Prophet forecast using full time series for an item"""
    # Extract all quantities for this item chronologically
    quantities = df[item_name].values

    if len(quantities) < 10 or sum(quantities) == 0:
        return None, None

    try:
        # Parse dates to proper datetime objects
        dates = []
        for date_str in df["Date"].values:
            # Parse "07/01 - Tuesday" format
            match = re.match(r"(\d+)/(\d+) - \w+", date_str)
            if match:
                month, day = match.groups()
                # Assume 2025 based on business start date
                date_obj = pd.to_datetime(f"2025-{month.zfill(2)}-{day.zfill(2)}")
                dates.append(date_obj)

        if len(dates) != len(quantities):
            return None, None

        # Create Prophet dataframe
        df_prophet = pd.DataFrame({"ds": dates, "y": quantities})

        # Sort chronologically
        df_prophet = df_prophet.sort_values("ds").reset_index(drop=True)

        # Find introduction point (after 7+ consecutive zeros)
        trim_idx = 0
        consecutive_zeros = 0
        for i, val in enumerate(df_prophet["y"].values):
            if val == 0:
                consecutive_zeros += 1
            else:
                if consecutive_zeros >= 7:
                    trim_idx = i
                consecutive_zeros = 0

        # Use post-introduction data if available
        if trim_idx > 0 and len(df_prophet) - trim_idx >= 5:
            df_prophet = df_prophet.iloc[trim_idx:].reset_index(drop=True)

        if len(df_prophet) < 5:
            return None, None

        # Create Prophet model with weekly seasonality
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,  # Enable to capture weekday patterns
            yearly_seasonality=False,
            interval_width=0.8,
        )
        model.fit(df_prophet)

        # Create future dates for forecasting
        future = model.make_future_dataframe(periods=forecast_days)
        forecast = model.predict(future)

        # Apply floor constraint to prevent negative predictions
        forecast["yhat"] = forecast["yhat"].clip(lower=0)
        forecast["yhat_lower"] = forecast["yhat_lower"].clip(lower=0)

        return forecast, model

    except Exception:
        return None, None


def generate_forecasts(df, weekday_data, logger=None):
    """Generate Prophet forecasts for all items and save as JSON data"""
    # Get item columns (exclude Date)
    item_columns = [col for col in df.columns if col != "Date"]
    forecast_mgr = get_forecast_manager()

    print(f"\nGenerating unified forecasts for {len(item_columns)} items...")

    successful_forecasts = 0

    for idx, item_name in enumerate(item_columns):
        print(f"Creating forecast for: {item_name} ({idx+1}/{len(item_columns)})")

        # Create unified Prophet model for this item
        forecast, _ = create_full_timeseries_forecast(df, item_name)

        if forecast is not None:
            # Prepare forecast data for storage
            forecast_data = {
                "forecast_df": forecast,
                "item_name": item_name,
                "model_type": "prophet_unified",
                "model_params": {
                    "weekly_seasonality": True,
                    "daily_seasonality": False,
                    "yearly_seasonality": False,
                    "interval_width": 0.8,
                },
                "historical_data": df[item_name].tolist(),
                "date_range": {
                    "start_date": df["Date"].iloc[0],
                    "end_date": df["Date"].iloc[-1],
                    "total_days": len(df),
                },
                "weekday_breakdown": {},
            }

            # Add weekday-specific historical data for plot rendering
            weekdays = [
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            for weekday in weekdays:
                weekday_indices = weekday_data[weekday]
                weekday_quantities = []
                dates = []
                date_labels = []

                for idx_row in weekday_indices:
                    quantity = df.iloc[idx_row][item_name] if item_name in df.columns else 0
                    weekday_quantities.append(quantity)

                    date_formatted = df.iloc[idx_row]["Date"]
                    dates.append(date_formatted)

                    # Parse "M/D - DayName" format to get just "M/D"
                    match = re.match(r"(\d+/\d+) - \w+", date_formatted)
                    if match:
                        date_str = match.group(1)
                        date_labels.append(date_str)
                    else:
                        date_labels.append(date_formatted)

                forecast_data["weekday_breakdown"][weekday] = {
                    "dates": dates,
                    "quantities": weekday_quantities,
                    "date_labels": date_labels,
                    "avg": (float(np.mean(weekday_quantities)) if weekday_quantities else 0.0),
                    "max": (float(np.max(weekday_quantities)) if weekday_quantities else 0.0),
                    "total_data_points": len(weekday_quantities),
                }

            # Save forecast data
            if forecast_mgr.save_item_forecast(item_name, forecast_data):
                successful_forecasts += 1
            else:
                print(f"  ⚠️  Failed to save forecast for {item_name}")
        else:
            print(f"  ⚠️  Could not generate forecast for {item_name}")

    print(f"\nSuccessfully generated and saved {successful_forecasts} forecasts to data/forecasts/")
    return successful_forecasts


def main():
    """Main forecast generation workflow"""
    logger = get_logger(__name__, "ForecastGenerator")

    with PerformanceLogger(logger, "forecast generation workflow", operation="main"):
        # Setup
        ensure_directories(logger)

        # Load and parse data
        df = load_quantity_data(logger)
        _, weekday_data = parse_date_rows(df)

        # Generate forecasts
        successful_count = generate_forecasts(df, weekday_data, logger)

        # Log final summary
        total_items = len([col for col in df.columns if col != "Date"])
        logger.info(
            "Forecast generation completed",
            extra={
                "items_processed": total_items,
                "forecasts_generated": successful_count,
                "success_rate": successful_count / total_items if total_items > 0 else 0,
            },
        )

    forecast_mgr = get_forecast_manager()
    available_forecasts = forecast_mgr.get_available_forecasts()
    print(f"Total Available Forecasts: {len(available_forecasts)} files")

    print("\n🚀 Forecast generation complete! Forecasts saved to data/forecasts/")
    print("💡 Use the Flask web app to view dynamic plots generated from this data.")
    print("   Run: python web/app.py")


if __name__ == "__main__":
    main()

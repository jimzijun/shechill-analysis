#!/usr/bin/env python3
"""
Dynamic Plot Renderer for SheChill Web App
==========================================

Renders matplotlib/seaborn plots on-demand in Flask using forecast data.
Uses BytesIO + base64 encoding for direct HTML embedding without file I/O.
"""

import base64
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Set backend for Flask compatibility
matplotlib.use("Agg")

# Set up logging using centralized config
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.logging_config import setup_logger

logger = setup_logger("PlotRenderer")

# Set up matplotlib/seaborn styling
plt.style.use("default")
sns.set_palette("husl")


class PlotRenderer:
    """Handles dynamic plot generation for web interface"""

    def __init__(self):
        """Initialize plot renderer with default settings"""
        self.figure_size = (12, 8)
        self.dpi = 150
        self.format = "png"

    def render_grid_plot(
        self,
        item_name: str,
        forecast_data: Dict[str, Any],
        quantity_data: Dict[str, Any],
    ) -> Optional[str]:
        """
        Render weekday grid plot for an item using forecast data

        Args:
            item_name: Name of the item
            forecast_data: Forecast data from forecast_manager
            quantity_data: Historical quantity data grouped by weekday

        Returns:
            base64-encoded PNG string or None if error
        """
        try:
            # Create figure with 6 subplots (2 rows, 3 columns)
            fig, axes = plt.subplots(2, 3, figsize=self.figure_size)
            fig.suptitle(
                f"Weekday Sales Pattern with Unified Forecast: {item_name}",
                fontsize=16,
                fontweight="bold",
            )

            weekdays = [
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]

            # Extract forecast DataFrame
            forecast_df = forecast_data.get("forecast_df")
            if forecast_df is None:
                return None

            # Convert to pandas DataFrame if it's in JSON format
            if isinstance(forecast_df, dict) and "data" in forecast_df:
                forecast_df = pd.DataFrame(forecast_df["data"])
                forecast_df["ds"] = pd.to_datetime(forecast_df["ds"])
            elif not isinstance(forecast_df, pd.DataFrame):
                logger.error(f"Unexpected forecast_df format: {type(forecast_df)}")
                return None

            for i, weekday in enumerate(weekdays):
                ax = axes[i // 3, i % 3]

                # Get historical data for this weekday
                historical_data = quantity_data.get(weekday, {})
                dates = historical_data.get("dates", [])
                quantities = historical_data.get("quantities", [])
                date_labels = historical_data.get("date_labels", [])

                # Plot historical data
                if quantities:
                    historical_x = range(len(quantities))
                    ax.plot(
                        historical_x,
                        quantities,
                        "o-",
                        linewidth=2,
                        markersize=4,
                        label="Historical",
                        color="blue",
                    )

                # Add complete predictions data (past and future)
                (
                    all_pred_x,
                    all_pred_y,
                    all_pred_lower,
                    all_pred_upper,
                    all_pred_labels,
                    future_start_idx,
                ) = self._extract_weekday_all_predictions(weekday, forecast_df, dates)

                if all_pred_x and all_pred_y:
                    # Plot complete prediction line
                    ax.plot(
                        all_pred_x,
                        all_pred_y,
                        "-",
                        linewidth=2,
                        color="red",
                        alpha=0.8,
                        label="Model Predictions",
                    )

                    # Highlight future portion with dashed line
                    if future_start_idx is not None and future_start_idx < len(all_pred_x):
                        future_x = all_pred_x[future_start_idx:]
                        future_y = all_pred_y[future_start_idx:]
                        ax.plot(
                            future_x,
                            future_y,
                            "--",
                            linewidth=3,
                            color="red",
                            label="Future Forecast",
                        )

                    # Plot confidence interval
                    ax.fill_between(
                        all_pred_x,
                        all_pred_lower,
                        all_pred_upper,
                        alpha=0.2,
                        color="red",
                        label="Confidence Interval",
                    )

                # Set up axes
                all_x = list(range(len(quantities))) + (all_pred_x[len(quantities) :] if all_pred_x else [])
                all_labels = date_labels + (all_pred_labels[len(quantities) :] if all_pred_labels else [])

                ax.set_title(f"{weekday}", fontweight="bold")
                ax.set_ylabel("Quantity Sold")
                ax.set_xlabel("Date")
                ax.grid(True, alpha=0.3)

                # Set x-axis labels
                if all_x:
                    ax.set_xticks(all_x)
                    ax.set_xticklabels(all_labels, rotation=45, ha="right")

                # Set y-axis to start at 0
                ax.set_ylim(bottom=0)

                # Add statistics
                next_forecast = (
                    all_pred_y[future_start_idx]
                    if all_pred_y and future_start_idx is not None and future_start_idx < len(all_pred_y)
                    else None
                )
                self._add_statistics_text(ax, quantities, [next_forecast] if next_forecast else [])

                # Add legend only to first subplot
                if i == 0 and all_pred_y:
                    ax.legend(loc="upper right", fontsize=8)

            plt.tight_layout()

            # Convert to base64
            img_buffer = BytesIO()
            plt.savefig(img_buffer, format=self.format, dpi=self.dpi, bbox_inches="tight")
            plt.close(fig)  # Important: close figure to prevent memory leaks

            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode("utf8")

            return img_base64

        except Exception as e:
            logger.error(f"Error rendering plot for {item_name}: {e}")
            plt.close("all")  # Clean up any open figures
            return None

    def render_simple_plot(self, item_name: str, forecast_data: Dict[str, Any]) -> Optional[str]:
        """
        Render simple time series plot for an item

        Args:
            item_name: Name of the item
            forecast_data: Forecast data from forecast_manager

        Returns:
            base64-encoded PNG string or None if error
        """
        try:
            # Create simple time series plot
            fig, ax = plt.subplots(1, 1, figsize=(12, 6))

            forecast_df = forecast_data.get("forecast_df")
            historical_data = forecast_data.get("historical_data")

            if forecast_df is None:
                return None

            # Plot forecast
            ax.plot(
                forecast_df["ds"],
                forecast_df["yhat"],
                label="Forecast",
                color="red",
                linestyle="--",
            )
            ax.fill_between(
                forecast_df["ds"],
                forecast_df["yhat_lower"],
                forecast_df["yhat_upper"],
                alpha=0.3,
                color="red",
                label="Confidence Interval",
            )

            # Plot historical data if available
            if historical_data is not None and len(historical_data) > 0:
                # Assume historical_data has matching dates
                hist_dates = forecast_df["ds"][: len(historical_data)]
                ax.plot(
                    hist_dates,
                    historical_data,
                    "o-",
                    label="Historical",
                    color="blue",
                    markersize=4,
                )

            ax.set_title(f"Sales Forecast: {item_name}", fontweight="bold")
            ax.set_ylabel("Quantity Sold")
            ax.set_xlabel("Date")
            ax.grid(True, alpha=0.3)
            ax.legend()

            plt.tight_layout()

            # Convert to base64
            img_buffer = BytesIO()
            plt.savefig(img_buffer, format=self.format, dpi=self.dpi, bbox_inches="tight")
            plt.close(fig)

            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode("utf8")

            return img_base64

        except Exception as e:
            logger.error(f"Error rendering simple plot for {item_name}: {e}")
            plt.close("all")
            return None

    def _extract_weekday_all_predictions(
        self, weekday: str, forecast_df: pd.DataFrame, historical_dates: list
    ) -> Tuple[list, list, list, list, list, int]:
        """Extract all prediction data (past and future) for a specific weekday"""
        try:
            # Map weekday names to numbers
            weekday_map = {
                "Monday": 0,
                "Tuesday": 1,
                "Wednesday": 2,
                "Thursday": 3,
                "Friday": 4,
                "Saturday": 5,
                "Sunday": 6,
            }
            target_weekday_num = weekday_map.get(weekday)

            if target_weekday_num is None:
                return [], [], [], [], [], None

            # Ensure ds column is datetime
            forecast_df = forecast_df.copy()
            if "ds" in forecast_df.columns:
                forecast_df["ds"] = pd.to_datetime(forecast_df["ds"])
            else:
                logger.error("No 'ds' column found in forecast data")
                return [], [], [], [], [], None

            # Filter all predictions for this specific weekday
            weekday_predictions = forecast_df[forecast_df["ds"].dt.dayofweek == target_weekday_num].copy()

            if weekday_predictions.empty:
                return [], [], [], [], [], None

            # Get last historical date to determine future start
            last_date = None
            if historical_dates:
                last_date_str = historical_dates[-1] if isinstance(historical_dates[-1], str) else None
                if last_date_str:
                    try:
                        import re

                        match = re.match(r"(\d+/\d+)", last_date_str)
                        if match:
                            date_part = match.group(1)
                            last_date = pd.to_datetime(f"2025/{date_part}")
                        else:
                            last_date = pd.to_datetime(last_date_str)
                    except Exception:
                        last_date = pd.Timestamp("2025-08-30")

            if last_date is None:
                last_date = pd.Timestamp("2025-08-30")

            # Prepare data for plotting - align with historical data positions
            all_pred_x = []
            all_pred_y = []
            all_pred_lower = []
            all_pred_upper = []
            all_pred_labels = []
            future_start_idx = None

            # First, add predictions that align with historical dates
            for i, hist_date in enumerate(historical_dates):
                # Find closest prediction date
                for _, pred_row in weekday_predictions.iterrows():
                    pred_date_str = pred_row["ds"].strftime("%m/%d")
                    hist_date_match = re.match(r"(\d+/\d+)", str(hist_date))
                    if hist_date_match:
                        hist_date_str = hist_date_match.group(1)
                        # Convert to MM/DD format for comparison
                        try:
                            month, day = hist_date_str.split("/")
                            hist_formatted = f"{int(month):02d}/{int(day):02d}"
                            if pred_date_str == hist_formatted:
                                all_pred_x.append(i)
                                all_pred_y.append(pred_row["yhat"])
                                all_pred_lower.append(pred_row["yhat_lower"])
                                all_pred_upper.append(pred_row["yhat_upper"])
                                all_pred_labels.append(hist_date)
                                break
                        except Exception:
                            continue

            # Then add future predictions
            future_predictions = weekday_predictions[weekday_predictions["ds"] > last_date].head(4)
            if not future_predictions.empty:
                future_start_idx = len(all_pred_x)
                start_idx = len(historical_dates)

                for i, (_, pred_row) in enumerate(future_predictions.iterrows()):
                    all_pred_x.append(start_idx + i)
                    all_pred_y.append(pred_row["yhat"])
                    all_pred_lower.append(pred_row["yhat_lower"])
                    all_pred_upper.append(pred_row["yhat_upper"])
                    all_pred_labels.append(f"F+{i+1}")

            return (
                all_pred_x,
                all_pred_y,
                all_pred_lower,
                all_pred_upper,
                all_pred_labels,
                future_start_idx,
            )

        except Exception as e:
            logger.error(f"Error extracting all predictions for {weekday}: {e}")
            return [], [], [], [], [], None

    def _extract_weekday_forecast(
        self, weekday: str, forecast_df: pd.DataFrame, historical_dates: list
    ) -> Tuple[list, list, list, list, list]:
        """Extract forecast data for a specific weekday"""
        try:
            # Map weekday names to numbers
            weekday_map = {
                "Monday": 0,
                "Tuesday": 1,
                "Wednesday": 2,
                "Thursday": 3,
                "Friday": 4,
                "Saturday": 5,
                "Sunday": 6,
            }
            target_weekday_num = weekday_map.get(weekday)

            if target_weekday_num is None:
                return [], [], [], [], []

            # Get last historical date
            last_date = None
            if historical_dates:
                # Parse the last historical date - handle "MM/DD - Weekday" format
                last_date_str = historical_dates[-1] if isinstance(historical_dates[-1], str) else None
                if last_date_str:
                    try:
                        # Extract date part from "MM/DD - Weekday" format

                        match = re.match(r"(\d+/\d+)", last_date_str)
                        if match:
                            date_part = match.group(1)
                            # Assume current year (2025 based on forecast data)
                            last_date = pd.to_datetime(f"2025/{date_part}")
                        else:
                            # Try direct parsing
                            last_date = pd.to_datetime(last_date_str)
                    except Exception as parse_error:
                        logger.warning(f"Could not parse date '{last_date_str}': {parse_error}")
                        # Use a reasonable fallback - end of August 2025
                        last_date = pd.Timestamp("2025-08-30")

            if last_date is None:
                # Default to end of August 2025 if no historical dates
                last_date = pd.Timestamp("2025-08-30")

            # Ensure ds column is datetime
            forecast_df = forecast_df.copy()
            if "ds" in forecast_df.columns:
                forecast_df["ds"] = pd.to_datetime(forecast_df["ds"])
            else:
                logger.error("No 'ds' column found in forecast data")
                return [], [], [], [], []

            # Filter forecast for this weekday and future dates
            future_forecast = forecast_df[forecast_df["ds"] > last_date].copy()

            if future_forecast.empty:
                return [], [], [], [], []

            # Get forecast points for this specific weekday (next 4 instances)
            weekday_forecast = future_forecast[future_forecast["ds"].dt.dayofweek == target_weekday_num].head(4)

            if weekday_forecast.empty:
                return [], [], [], [], []

            # Prepare data for plotting
            start_idx = len(historical_dates)
            forecast_x = [start_idx + i for i in range(len(weekday_forecast))]
            forecast_y = weekday_forecast["yhat"].tolist()
            forecast_lower = weekday_forecast["yhat_lower"].tolist()
            forecast_upper = weekday_forecast["yhat_upper"].tolist()
            forecast_labels = [f"F+{i+1}" for i in range(len(weekday_forecast))]

            return (
                forecast_x,
                forecast_y,
                forecast_lower,
                forecast_upper,
                forecast_labels,
            )

        except Exception as e:
            logger.error(f"Error extracting weekday forecast for {weekday}: {e}")
            return [], [], [], [], []

    def _add_statistics_text(self, ax, quantities: list, forecast_y: list):
        """Add statistics text box to plot"""
        try:
            if not quantities:
                return

            avg_qty = np.mean(quantities)
            max_qty = np.max(quantities)

            stats_text = f"Avg: {avg_qty:.1f}\nMax: {max_qty:.0f}"

            if forecast_y:
                next_forecast = forecast_y[0]
                stats_text += f"\nNext: {next_forecast:.1f}"

            ax.text(
                0.98,
                0.98,
                stats_text,
                transform=ax.transAxes,
                verticalalignment="top",
                horizontalalignment="right",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
            )
        except Exception as e:
            logger.warning(f"Could not add statistics text: {e}")


# Global instance
plot_renderer = PlotRenderer()


def get_plot_renderer() -> PlotRenderer:
    """Get the global plot renderer instance"""
    return plot_renderer


def render_item_plot(
    item_name: str,
    forecast_data: Dict[str, Any],
    quantity_data: Dict[str, Any],
    plot_type: str = "grid",
) -> Optional[str]:
    """
    Convenience function to render plots with caching support

    Args:
        item_name: Name of the item
        forecast_data: Forecast data from forecast_manager
        quantity_data: Historical quantity data
        plot_type: 'grid' or 'simple' (only grid plots are cached and used)

    Returns:
        base64-encoded PNG string or None
    """
    # For grid plots (the only type used in production), use caching
    if plot_type == "grid":
        try:
            from plot_cache import get_plot_cache

            # Get cache instance
            cache = get_plot_cache()

            # Get timestamps for cache invalidation
            forecast_timestamp = forecast_data.get("metadata", {}).get("generated_at", "")
            historical_timestamp = cache._get_historical_timestamp()

            # Try to get from cache first
            cached_plot = cache.get_cached_plot(item_name, plot_type, forecast_timestamp, historical_timestamp)
            if cached_plot:
                return cached_plot

            # Generate plot if not cached
            renderer = get_plot_renderer()
            plot_base64 = renderer.render_grid_plot(item_name, forecast_data, quantity_data)

            # Cache the generated plot
            if plot_base64:
                cache.cache_plot(item_name, plot_type, forecast_timestamp, historical_timestamp, plot_base64)

            return plot_base64

        except ImportError:
            # Fallback if cache not available - render directly
            renderer = get_plot_renderer()
            return renderer.render_grid_plot(item_name, forecast_data, quantity_data)
        except Exception as e:
            logger.warning(f"Cache error for {item_name}, falling back to direct render: {e}")
            renderer = get_plot_renderer()
            return renderer.render_grid_plot(item_name, forecast_data, quantity_data)

    # For simple plots (only used in testing), render directly without caching
    elif plot_type == "simple":
        renderer = get_plot_renderer()
        return renderer.render_simple_plot(item_name, forecast_data)
    else:
        logger.error(f"Unknown plot type: {plot_type}")
        return None


if __name__ == "__main__":
    # Test plot renderer
    logger.info("Plot Renderer Test")
    logger.info("=" * 40)

    # Create test data
    test_forecast_data = {
        "forecast_df": pd.DataFrame(
            {
                "ds": pd.date_range("2025-01-01", periods=30),
                "yhat": np.random.rand(30) * 100,
                "yhat_lower": np.random.rand(30) * 80,
                "yhat_upper": np.random.rand(30) * 120,
            }
        )
    }

    test_quantity_data = {
        "Tuesday": {
            "dates": ["2025-01-01", "2025-01-08"],
            "quantities": [10, 15],
            "date_labels": ["1/1", "1/8"],
        }
    }

    renderer = PlotRenderer()
    result = renderer.render_simple_plot("Test Item", test_forecast_data)

    logger.info(f"Test render successful: {result is not None}")
    if result:
        logger.info(f"Base64 length: {len(result)} characters")

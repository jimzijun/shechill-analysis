"""
Enhanced Shechill Patisserie Quantity Analysis Script
=====================================================

This script processes live JSON transaction data from Square API to generate
daily quantity analysis by item for forecasting purposes.

Data Flow:
- Reads JSON files from data/raw_transactions/
- Processes live transaction data with item mapping and filtering
- Creates analysis-ready CSV for Prophet forecasting
- Supports both incremental updates and full rebuilds

Output Files:
- data/quantity_per_day_per_item.csv - Daily quantities by item with category
"""

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from src.logging_config import PerformanceLogger, get_logger


class QuantityAnalyzer:
    """Enhanced quantity analysis with JSON data support"""

    def __init__(self, data_dir: str = "data"):
        """Initialize analyzer with data directory"""
        self.data_dir = Path(data_dir)
        self.raw_data_dir = self.data_dir / "raw_transactions"
        self.output_file = self.data_dir / "quantity_per_day_per_item.csv"
        self.logger = get_logger(__name__, "QuantityAnalyzer")

        # Create directories if needed
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            "QuantityAnalyzer initialized", extra={"data_dir": str(self.data_dir), "output_file": str(self.output_file)}
        )

    def load_json_transactions(self) -> pd.DataFrame:
        """Load and combine all JSON raw order files from Square API"""
        self.logger.info("Loading raw order data from Square API")

        if not self.raw_data_dir.exists():
            self.logger.error("Raw data directory not found", extra={"raw_data_dir": str(self.raw_data_dir)})
            return pd.DataFrame()

        # Find all JSON files (skip last_fetch.json)
        json_files = [f for f in self.raw_data_dir.glob("*.json") if f.name != "last_fetch.json"]
        if not json_files:
            self.logger.warning("No raw order JSON files found", extra={"raw_data_dir": str(self.raw_data_dir)})
            return pd.DataFrame()

        self.logger.info("Found raw order files", extra={"file_count": len(json_files)})

        # Process raw orders into transaction records
        all_transactions = []
        total_orders = 0
        total_items = 0

        for json_file in sorted(json_files):
            try:
                with open(json_file, "r") as f:
                    daily_orders = json.load(f)

                if not daily_orders:
                    continue

                orders_processed = 0
                items_processed = 0

                for order in daily_orders:
                    # Extract order metadata
                    order_id = order.get("id", "")
                    created_at = order.get("created_at", "")
                    order_date = order.get("date", "")  # Already set by Square API client
                    local_datetime = order.get("local_datetime", "")

                    if not created_at or not order_date:
                        continue

                    # Parse the local datetime for day of week
                    try:
                        if local_datetime:
                            dt = pd.to_datetime(local_datetime)
                        else:
                            # Fallback to created_at
                            dt = pd.to_datetime(created_at)
                        day_of_week = dt.day_name()
                    except Exception:
                        day_of_week = "Unknown"

                    # Process line items
                    line_items = order.get("line_items", [])
                    for item in line_items:
                        if not item:
                            continue

                        # Extract item details
                        item_name = item.get("name", "").strip()
                        if not item_name:
                            continue

                        try:
                            quantity = float(item.get("quantity", "0"))
                        except (ValueError, TypeError):
                            quantity = 0.0

                        if quantity <= 0:
                            continue

                        # Get price (Square amounts are in cents)
                        sales_price = 0.0
                        base_price_money = item.get("base_price_money", {})
                        if base_price_money:
                            try:
                                amount = base_price_money.get("amount", 0)
                                sales_price = float(amount) / 100.0
                            except (KeyError, ValueError, TypeError):
                                pass

                        # Create transaction record
                        all_transactions.append(
                            {
                                "Item": item_name,
                                "Qty": quantity,
                                "Date": order_date,
                                "Net Sales": sales_price,
                                "Day_of_Week": day_of_week,
                                "order_id": order_id,
                                "created_at": created_at,
                            }
                        )

                        items_processed += 1

                    orders_processed += 1

                total_orders += orders_processed
                total_items += items_processed
                print(f"   {json_file.name}: {orders_processed} orders, {items_processed} line items")

            except Exception as e:
                print(f"⚠️  Error loading {json_file.name}: {e}")
                continue

        if not all_transactions:
            print("❌ No valid transaction data found")
            return pd.DataFrame()

        print(f"Total orders processed: {total_orders:,}")
        print(f"Total line items processed: {total_items:,}")

        # Convert to DataFrame
        df = pd.DataFrame(all_transactions)

        # Convert Date to datetime and ensure proper format
        df["Date"] = pd.to_datetime(df["Date"])

        # Filter out zero quantities
        df = df[df["Qty"] > 0].copy()

        print(f"Valid transactions after filtering: {len(df):,}")
        print(f"Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")
        print(f"Unique items: {df['Item'].nunique()}")

        return df

    def clean_item_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and merge duplicate/similar item names"""
        print("\nCleaning item names...")

        # Enhanced merge mappings for both CSV and JSON data
        item_mappings = {
            # Exact duplicates and trailing spaces
            "Berry Tart": ["Berry Tart", "Berry Tart "],
            "Chocolate Tart": ["Chocolate Tart", "Chocolate Tart "],
            "Bread Pudding Croissant": ["Bread Pudding Croissant"],
            "Chocolate Banana Bread (Gluten Free)": ["Chocolate Banana Bread (Gluten Free)"],
            "Crispy Egg Tart": ["Crispy Egg Tart", "Egg Tart"],
            # Spelling/character variations
            "Dubai Chocolate Croissant": [
                "Dubai Chocolate Croissant",
                "Dubaï Chocolate Croissant",
                "Dubai Chocolate Croissant (Fri/Sat/Sun)",
            ],
            "Mini Black Sesame Croissant": [
                "Mini Black Sesame Croissant",
                "Mini Black SésameCroissant",
                "Mini Black Sesame Croissant (Fri/Sat/Sun)",
            ],
            "Croque Monsieur": ["CroqueMonsieur", "Croque Monsieur"],
            # Weekend/special variations
            "Avocado Egg Croissant Sandwich": [
                "Avocado Egg Croissant Sandwich",
                "Avocado Egg Croissant Sandwich (Fri/Sat/Sun)",
                "Avocado Egg Croissant Sandwich - Weekend Only",
            ],
            "Black Sesame Croissant": [
                "Black Sesame Croissant",
                "Black Sesame Croissant (Fri/Sat/Sun)",
                "Black Sesame Croissant Toast - Weekend Only",
            ],
            "Brie Prosciutto Croissant Sandwich": [
                "Brie Prosciutto Croissant Sandwich",
                "Brie Prosciutto Croissant Sandwich (Fri/Sat/Sun)",
                "Brie Prosciutto Croissant Sandwich - Weekend Only",
            ],
            "Red Bow Tie Croissant": [
                "Red Bow Tie Croissant",
                "Red Bow Tie Croissant (Fri/Sat/Sun)",
                "Red Bow Tie Croissant - Weekend Only",
            ],
            # Size/format variations
            "Lemon Tart (Large)": ["Lemon Tart (L)", "Lemon Tart (Large)"],
            "Raspberry Tart (Small)": ["Raspberry Tart (Small)", "Raspberry Tart(S)"],
            # Ampersand variations (JSON vs CSV differences)
            "Ham & Cheese Croissant": [
                "Ham & Cheese Croissant",
                "Ham  Cheese Croissant",
            ],
        }

        # Create reverse mapping for faster lookup
        reverse_mapping = {}
        for target, sources in item_mappings.items():
            for source in sources:
                reverse_mapping[source] = target

        # Apply cleaning
        df_cleaned = df.copy()
        original_items = df_cleaned["Item"].nunique()

        # Show some examples before cleaning
        duplicates_before = df_cleaned["Item"].value_counts()
        duplicate_items = duplicates_before[duplicates_before > 1]
        if len(duplicate_items) > 5:
            print(f"Sample duplicates before cleaning: {dict(duplicate_items.head().items())}")

        # Apply mapping
        df_cleaned["Item"] = df_cleaned["Item"].map(reverse_mapping).fillna(df_cleaned["Item"])

        cleaned_items = df_cleaned["Item"].nunique()
        merged_count = original_items - cleaned_items

        print(f"Items before cleaning: {original_items}")
        print(f"Items after cleaning: {cleaned_items}")
        print(f"Items merged: {merged_count}")

        return df_cleaned

    def apply_daily_cutoff(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply 10 PM cutoff rule for incomplete daily data"""
        from datetime import datetime, time

        import pandas as pd

        now = datetime.now()
        cutoff_time = time(22, 0)  # 10 PM
        today = pd.to_datetime(now.date())  # Convert to pandas datetime for comparison

        print("\n🕰️  Applying daily cutoff logic...")
        print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("Cutoff time: 22:00 (10 PM)")

        if now.time() < cutoff_time:
            # Before 10 PM - exclude today's data to avoid incomplete daily data
            df_filtered = df[df["Date"] < today].copy()
            excluded_count = len(df) - len(df_filtered)
            print(f"🕘 Before 10 PM cutoff - excluding today's data ({today.date()})")
            print(f"Excluded transactions: {excluded_count:,}")
            print("Reason: Incomplete daily data affects forecasting accuracy")
        else:
            # After 10 PM - include all data (today should be complete)
            df_filtered = df.copy()
            print("🕙 After 10 PM cutoff - including all data through today")
            print(f"All transactions retained: {len(df_filtered):,}")

        return df_filtered

    def create_quantity_pivot(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create daily quantity pivot table with metadata"""
        print("\nCreating quantity pivot table...")

        print(f"Original data: {len(df):,} transactions")

        df_filtered = df.copy()

        # Filter out Monday data (bakery is closed)
        df_filtered = df_filtered[df_filtered["Day_of_Week"] != "Monday"].copy()
        print(f"After removing Monday: {len(df_filtered):,} transactions")

        # Apply daily cutoff logic to prevent incomplete daily data from affecting forecasts
        df_filtered = self.apply_daily_cutoff(df_filtered)
        print(f"After daily cutoff: {len(df_filtered):,} transactions")

        print("Excluded days: Monday (bakery closed)")

        # Clean item names to merge duplicates
        df_filtered = self.clean_item_names(df_filtered)

        # Remove seasonal/special items (4th of July, Easter specials)
        print("Removing seasonal/special items...")
        before_special_filter = len(df_filtered)
        df_filtered = df_filtered[
            ~df_filtered["Item"].str.contains("4th of July|4th Of July|Easter Special", case=False, na=False)
        ]
        after_special_filter = len(df_filtered)
        removed_special = before_special_filter - after_special_filter
        print(f"Removed {removed_special} transactions for seasonal/special items")

        # Group by Date and Item only
        daily_qty = df_filtered.groupby(["Date", "Item"]).agg({"Qty": "sum"}).reset_index()

        print(f"Daily aggregated data shape: {daily_qty.shape}")
        print(f"Unique items: {daily_qty['Item'].nunique()}")

        # Create pivot table - Dates as rows, Items as columns
        qty_pivot = daily_qty.pivot_table(index="Date", columns="Item", values="Qty", fill_value=0).reset_index()

        # Format the Date column and add day of week
        qty_pivot["Date_Formatted"] = qty_pivot["Date"].dt.strftime("%m/%d") + " - " + qty_pivot["Date"].dt.day_name()

        # Reorder columns: Date_Formatted first, then all items sorted alphabetically
        item_columns = [col for col in qty_pivot.columns if col not in ["Date", "Date_Formatted"]]
        item_columns.sort()  # Sort items alphabetically

        # Build final column order
        new_columns = ["Date_Formatted"] + item_columns
        qty_pivot = qty_pivot[new_columns]

        # Rename Date_Formatted to Date for cleaner output
        qty_pivot = qty_pivot.rename(columns={"Date_Formatted": "Date"})

        print(f"Final pivot table shape: {qty_pivot.shape}")
        print("Table format: Dates as rows, Items as columns")
        print("Items ordered alphabetically")
        print("Excluded: Seasonal/special items, Monday, problematic dates")

        return qty_pivot

    def generate_basic_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate basic statistics for summary"""
        df_filtered = df.copy()

        # Filter out Monday data (bakery is closed)
        df_filtered = df_filtered[df_filtered["Day_of_Week"] != "Monday"].copy()

        total_qty = df_filtered["Qty"].sum()
        unique_items = df_filtered["Item"].nunique()
        date_range = (df["Date"].min(), df["Date"].max())

        return {
            "total_qty": total_qty,
            "unique_items": unique_items,
            "date_range": date_range,
            "total_days": (date_range[1] - date_range[0]).days + 1,
        }

    def save_files(self, qty_pivot: pd.DataFrame):
        """Save output files to data directory"""
        print("\nSaving files...")

        # Save quantity pivot table
        qty_pivot.to_csv(self.output_file, index=False)

        print("\n=== FILES CREATED ===")
        print("Data files:")
        print(f"  - {self.output_file}")

    def run_analysis(self):
        """Main analysis workflow"""
        with PerformanceLogger(self.logger, "quantity analysis workflow", operation="run_analysis"):
            # Load and process data
            df = self.load_json_transactions()
            if df.empty:
                self.logger.warning("No transaction data available for analysis")
                return

            qty_pivot = self.create_quantity_pivot(df)
            stats = self.generate_basic_stats(df)

            # Save results
            self.save_files(qty_pivot)

            # Log results
            self.logger.info(
                "Analysis completed successfully",
                extra={
                    "output_file": str(self.output_file),
                    "items_processed": len(qty_pivot.columns) - 1 if not qty_pivot.empty else 0,
                    "date_range_days": len(qty_pivot) if not qty_pivot.empty else 0,
                },
            )

        # Print summary
        print("\n=== ANALYSIS SUMMARY ===")
        print("Data Source: JSON (Square API)")
        print(f"Period: {stats['date_range'][0].strftime('%Y-%m-%d')} to {stats['date_range'][1].strftime('%Y-%m-%d')}")
        print(f"Total Quantity: {stats['total_qty']:,.0f} units")
        print(f"Items Analyzed: {stats['unique_items']} unique items (after data cleaning)")
        print(f"Days Covered: {stats['total_days']} days")

        print("\nQuantity analysis complete! Check the data/ directory for outputs.")

        return qty_pivot, stats


def main():
    """Main function for CLI usage"""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Quantity Analysis with JSON support")
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data)")

    args = parser.parse_args()

    try:
        analyzer = QuantityAnalyzer(data_dir=args.data_dir)
        analyzer.run_analysis()

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

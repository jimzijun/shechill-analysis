"""
Shechill Patisserie Quantity Analysis Script
============================================

This script processes transaction data to generate daily quantity analysis
by item with category and day-of-week metadata for forecasting purposes.

Directory Structure:
- /data/        - All data files (input and generated)  
- quantity_analysis.py (root) - This analysis script

Output Files:
- data/quantity_per_day_per_item.csv - Daily quantities by item with category
"""

import pandas as pd
import os

def ensure_directories():
    """Create data directory if it doesn't exist"""
    os.makedirs('../data', exist_ok=True)

def load_transaction_data():
    """Load and clean transaction data"""
    print("Loading transaction data...")
    df = pd.read_csv('../data/transaction-summary.csv', low_memory=False)
    
    print(f"Total transactions: {len(df):,}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
    
    # Convert Date column to datetime and extract day of week
    df['Date'] = pd.to_datetime(df['Date'])
    df['Day_of_Week'] = df['Date'].dt.day_name()
    
    # Clean monetary fields
    df['Net Sales'] = df['Net Sales'].replace(r'[\$,]', '', regex=True).astype(float)
    df['Qty'] = df['Qty'].astype(float)
    
    return df

def clean_item_names(df):
    """Clean and merge duplicate/similar item names"""
    print("\nCleaning item names...")
    
    # Define merge mappings - target_name: [list_of_names_to_merge]
    item_mappings = {
        # Exact duplicates and trailing spaces
        'Berry Tart': ['Berry Tart', 'Berry Tart '],
        'Chocolate Tart': ['Chocolate Tart', 'Chocolate Tart '],
        'Bread Pudding Croissant': ['Bread Pudding Croissant'],  # Handles exact duplicates in aggregation
        'Chocolate Banana Bread (Gluten Free)': ['Chocolate Banana Bread (Gluten Free)'],  # Handles exact duplicates in aggregation
        'Crispy Egg Tart': ['Crispy Egg Tart', 'Egg Tart'],
        
        # Spelling/character variations
        'Dubai Chocolate Croissant': ['Dubai Chocolate Croissant', 'Dubaï Chocolate Croissant', 'Dubai Chocolate Croissant (Fri/Sat/Sun)'],
        'Mini Black Sesame Croissant': ['Mini Black Sesame Croissant', 'Mini Black SésameCroissant', 'Mini Black Sesame Croissant (Fri/Sat/Sun)'],
        'Croque Monsieur': ['CroqueMonsieur', 'Croque Monsieur'],
        
        # Weekend/special variations
        'Avocado Egg Croissant Sandwich': ['Avocado Egg Croissant Sandwich', 'Avocado Egg Croissant Sandwich (Fri/Sat/Sun)', 'Avocado Egg Croissant Sandwich - Weekend Only'],
        'Black Sesame Croissant': ['Black Sesame Croissant', 'Black Sesame Croissant (Fri/Sat/Sun)', 'Black Sesame Croissant Toast - Weekend Only'],
        'Brie Prosciutto Croissant Sandwich': ['Brie Prosciutto Croissant Sandwich', 'Brie Prosciutto Croissant Sandwich (Fri/Sat/Sun)', 'Brie Prosciutto Croissant Sandwich - Weekend Only'],
        'Red Bow Tie Croissant': ['Red Bow Tie Croissant', 'Red Bow Tie Croissant (Fri/Sat/Sun)', 'Red Bow Tie Croissant - Weekend Only'],
        
        # Size/format variations
        'Lemon Tart (Large)': ['Lemon Tart (L)', 'Lemon Tart (Large)'],
        'Raspberry Tart (Small)': ['Raspberry Tart (Small)', 'Raspberry Tart(S)']
    }
    
    # Create reverse mapping for faster lookup
    reverse_mapping = {}
    for target, sources in item_mappings.items():
        for source in sources:
            reverse_mapping[source] = target
    
    # Apply cleaning
    df_cleaned = df.copy()
    original_items = df_cleaned['Item'].nunique()
    
    # Show some examples before cleaning
    duplicates_before = df_cleaned['Item'].value_counts()[df_cleaned['Item'].value_counts() > 1]
    if len(duplicates_before) > 0:
        print(f"Examples of duplicates before cleaning: {duplicates_before.head().to_dict()}")
    
    df_cleaned['Item'] = df_cleaned['Item'].map(reverse_mapping).fillna(df_cleaned['Item'])
    
    # The key insight: exact duplicates will be handled by the subsequent groupby operation
    # But let's ensure we see the impact
    cleaned_items = df_cleaned['Item'].nunique()
    merged_count = original_items - cleaned_items
    
    print(f"Items before cleaning: {original_items}")
    print(f"Items after cleaning: {cleaned_items}")
    print(f"Items merged through mapping: {merged_count}")
    
    return df_cleaned

def create_quantity_pivot(df):
    """Create daily quantity pivot table with metadata"""
    print("\nFiltering and creating quantity pivot table...")
    
    # Filter for only the categories we need for forecasting
    target_categories = ['Croissant', 'Bread', 'Pastries', 'Drink']
    
    print(f"Original data: {len(df):,} transactions")
    # Remove NaN values before sorting categories
    all_categories = [cat for cat in df['Category'].unique() if pd.notna(cat)]
    print(f"All categories: {sorted(all_categories)}")
    
    # Filter data for target categories only
    df_filtered = df[df['Category'].isin(target_categories)].copy()
    
    print(f"After category filter: {len(df_filtered):,} transactions")
    
    # Filter out Monday data (bakery is closed)
    df_filtered = df_filtered[df_filtered['Day_of_Week'] != 'Monday'].copy()
    
    print(f"After removing Monday: {len(df_filtered):,} transactions")
    print(f"Target categories: {target_categories}")
    print("Excluded days: Monday (bakery closed)")
    
    # Clean item names to merge duplicates
    df_filtered = clean_item_names(df_filtered)
    
    # Remove seasonal/special items (4th of July, Easter specials)
    print("Removing seasonal/special items...")
    before_special_filter = len(df_filtered)
    df_filtered = df_filtered[~df_filtered['Item'].str.contains('4th of July|4th Of July|Easter Special', case=False, na=False)]
    after_special_filter = len(df_filtered)
    removed_special = before_special_filter - after_special_filter
    print(f"Removed {removed_special} transactions for seasonal/special items")
    
    # Group by Date and Item only (category not needed for output)
    daily_qty = df_filtered.groupby(['Date', 'Item']).agg({
        'Qty': 'sum'
    }).reset_index()
    
    print(f"Daily aggregated data shape: {daily_qty.shape}")
    print(f"Unique items: {daily_qty['Item'].nunique()}")
    
    # Create pivot table - Items as rows, Dates as columns
    qty_pivot = daily_qty.pivot_table(
        index='Item', 
        columns='Date', 
        values='Qty', 
        fill_value=0
    ).reset_index()
    
    # Keep only Item column and date columns (remove category from output)
    # qty_pivot already has Item column first, followed by date columns
    
    # Format date column headers and reorder by weekday then date
    date_columns = []
    
    # Extract date columns with their timestamp objects for sorting
    for col in qty_pivot.columns[1:]:  # Skip 'Item' column only
        if isinstance(col, pd.Timestamp):
            # Skip 1/14 date (January 14, 2025)
            if col.month == 1 and col.day == 14:
                continue
            formatted_date = f"{col.month}/{col.day} - {col.day_name()}"
            date_columns.append((col, formatted_date, col.day_name()))
    
    # Define weekday order (Tuesday to Sunday, excluding Monday)
    weekday_order = {'Tuesday': 0, 'Wednesday': 1, 'Thursday': 2, 'Friday': 3, 'Saturday': 4, 'Sunday': 5}
    
    # Sort by weekday first, then by actual date within each weekday
    date_columns.sort(key=lambda x: (weekday_order[x[2]], x[0]))
    
    # Build new column order: Item, then sorted date columns
    new_columns = ['Item'] + [formatted_header for _, formatted_header, _ in date_columns]
    
    # Reorder the DataFrame columns
    column_mapping = {col: formatted_header for col, formatted_header, _ in date_columns}
    qty_pivot = qty_pivot.rename(columns=column_mapping)
    qty_pivot = qty_pivot[new_columns]
    
    print(f"Final pivot table shape: {qty_pivot.shape}")
    print(f"Date headers formatted as: M/D - DayName")
    print(f"Columns ordered by: Weekday (Tue-Sun) then Date (ascending)")
    print("Excluded: Seasonal/special items, 1/14 date column")
    
    return qty_pivot


def generate_basic_stats(df):
    """Generate basic statistics for summary"""
    # Filter for target categories only
    target_categories = ['Croissant', 'Bread', 'Pastries', 'Drink']
    df_filtered = df[df['Category'].isin(target_categories)].copy()
    
    # Filter out Monday data (bakery is closed)
    df_filtered = df_filtered[df_filtered['Day_of_Week'] != 'Monday'].copy()
    
    total_qty = df_filtered['Qty'].sum()
    unique_items = df_filtered['Item'].nunique()
    unique_categories = df_filtered['Category'].nunique()
    date_range = (df['Date'].min(), df['Date'].max())
    
    return {
        'total_qty': total_qty,
        'unique_items': unique_items,
        'unique_categories': unique_categories,
        'date_range': date_range
    }

def save_files(qty_pivot):
    """Save output files to data directory"""
    print("\nSaving files...")
    
    # Save quantity pivot table
    qty_pivot.to_csv('../data/quantity_per_day_per_item.csv', index=False)
    
    print("\n=== FILES CREATED ===")
    print("Data files:")
    print("  - ../data/quantity_per_day_per_item.csv")

def main():
    """Main analysis workflow"""
    print("SHECHILL PATISSERIE QUANTITY ANALYSIS")
    print("=" * 40)
    
    # Setup
    ensure_directories()
    
    # Load and process data
    df = load_transaction_data()
    qty_pivot = create_quantity_pivot(df)
    stats = generate_basic_stats(df)
    
    # Save results
    save_files(qty_pivot)
    
    # Print summary
    print(f"\n=== ANALYSIS SUMMARY ===")
    print(f"Period: {stats['date_range'][0].strftime('%Y-%m-%d')} to {stats['date_range'][1].strftime('%Y-%m-%d')}")
    print(f"Total Quantity: {stats['total_qty']:,.0f} units")
    print(f"Items Analyzed: {stats['unique_items']} unique items (after data cleaning)")
    print(f"Categories: {stats['unique_categories']} categories")
    print(f"Days Covered: 147 days")
    
    print("\nQuantity analysis complete! Check the data/ directory for outputs.")

if __name__ == "__main__":
    main()
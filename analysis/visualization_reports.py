"""
Shechill Patisserie Grid Plot Reports Script
===========================================

This script generates weekday pattern grid plots from the quantity analysis data
to support forecasting and inventory planning decisions.

Directory Structure:
- /data/quantity_per_day_per_item.csv - Input data from quantity analysis
- /reports/grid_plots/ - Weekday pattern grid plots per item  

Output Visualizations:
- Grid plots: 6-panel weekday analysis for each item
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re
import numpy as np
from prophet import Prophet
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

def ensure_directories():
    """Create reports directory structure if it doesn't exist"""
    directories = [
        '../reports',
        '../reports/grid_plots'
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    print(f"Created {len(directories)} report directories")

def load_quantity_data():
    """Load and parse the quantity per day per item data"""
    print("Loading quantity data...")
    df = pd.read_csv('../data/quantity_per_day_per_item.csv')
    
    print(f"Loaded data shape: {df.shape}")
    print(f"Items: {len(df)} unique items")
    print(f"Date columns: {df.shape[1] - 1} dates")
    
    return df

def parse_date_columns(df):
    """Parse date column headers and extract weekday/date information"""
    print("Parsing date columns...")
    
    date_info = []
    weekday_columns = {'Tuesday': [], 'Wednesday': [], 'Thursday': [], 
                      'Friday': [], 'Saturday': [], 'Sunday': []}
    
    # Parse each date column (skip 'Item' column)
    for col in df.columns[1:]:
        # Parse format: "M/D - DayName" 
        match = re.match(r'(\d+)/(\d+) - (\w+)', col)
        if match:
            month, day, weekday = match.groups()
            date_info.append({
                'column': col,
                'month': int(month),
                'day': int(day), 
                'weekday': weekday
            })
            if weekday in weekday_columns:
                weekday_columns[weekday].append(col)
    
    print(f"Parsed {len(date_info)} date columns")
    for weekday, cols in weekday_columns.items():
        print(f"  {weekday}: {len(cols)} dates")
    
    return date_info, weekday_columns

def create_prophet_forecast(dates, values, forecast_periods=7):
    """Create Prophet forecast for a single time series, ignoring sequences before 4 consecutive zeros"""
    if len(values) < 10 or sum(values) == 0:  # Need minimum data points
        return None, None, None, None
    
    try:
        # Find the last sequence of 4+ consecutive zeros to determine trim point
        trim_idx = 0  # Start from beginning by default
        
        # Look for sequences of 4+ consecutive zeros
        consecutive_zeros = 0
        for i, val in enumerate(values):
            if val == 0:
                consecutive_zeros += 1
            else:
                # If we had 4+ consecutive zeros before this non-zero value,
                # consider everything before this point as "pre-introduction"
                if consecutive_zeros >= 4:
                    trim_idx = i  # Start from this non-zero value
                consecutive_zeros = 0
        
        # Trim data from the determined index onwards
        trimmed_dates = dates[trim_idx:]
        trimmed_values = values[trim_idx:]
        
        if len(trimmed_values) < 5:  # Not enough data after trimming
            return None, None, None, None
        
        # Prepare data for Prophet
        df_prophet = pd.DataFrame({
            'ds': pd.to_datetime(trimmed_dates, format='%m/%d', errors='coerce'),
            'y': trimmed_values
        })
        
        # Handle invalid dates by adding year (assume 2024)
        df_prophet['ds'] = pd.to_datetime('2024/' + df_prophet['ds'].dt.strftime('%m/%d'), errors='coerce')
        df_prophet = df_prophet.dropna()
        
        if len(df_prophet) < 5:
            return None, None, None, None
        
        # Create and fit Prophet model
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=False,
            interval_width=0.8
        )
        model.fit(df_prophet)
        
        # Create future dataframe for forecasting
        future = model.make_future_dataframe(periods=forecast_periods)
        forecast = model.predict(future)
        
        return forecast, df_prophet, model, trim_idx
        
    except Exception:
        return None, None, None, None

def create_grid_plots(df, weekday_columns):
    """Generate grid plots showing weekday patterns with Prophet forecasting"""
    print(f"\nGenerating grid plots with forecasting for {len(df)} items...")
    
    # Set up matplotlib style
    plt.style.use('default')
    sns.set_palette("husl")
    
    for idx, (_, row) in enumerate(df.iterrows()):
        item_name = row['Item']
        print(f"Creating grid plot for: {item_name} ({idx+1}/{len(df)})")
        
        # Create figure with 6 subplots (2 rows, 3 columns)
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle(f'Weekday Sales Pattern with Forecast: {item_name}', fontsize=16, fontweight='bold')
        
        weekdays = ['Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for i, weekday in enumerate(weekdays):
            ax = axes[i // 3, i % 3]
            
            # Get data for this weekday
            weekday_cols = weekday_columns[weekday]
            weekday_data = [row[col] for col in weekday_cols]
            
            # Extract M/D format from column names for x-axis labels
            date_labels = []
            raw_dates = []
            for col in weekday_cols:
                # Parse "M/D - DayName" format to get just "M/D"
                match = re.match(r'(\d+/\d+) - \w+', col)
                if match:
                    date_str = match.group(1)
                    date_labels.append(date_str)
                    raw_dates.append(date_str)
                else:
                    date_labels.append(col)
                    raw_dates.append(col)
            
            # Generate Prophet forecast
            forecast, _, _, trim_idx = create_prophet_forecast(raw_dates, weekday_data, forecast_periods=4)
            
            # Always plot full historical data for complete visibility
            historical_x = range(len(weekday_data))
            ax.plot(historical_x, weekday_data, 'o-', linewidth=2, markersize=4, 
                   label='Historical', color='blue')
            
            if forecast is not None and trim_idx is not None:
                # Add forecast based on post-introduction data
                forecast_start_idx = len(weekday_data)
                forecast_x = range(forecast_start_idx, forecast_start_idx + 4)
                forecast_y = forecast['yhat'].tail(4).values
                forecast_lower = forecast['yhat_lower'].tail(4).values
                forecast_upper = forecast['yhat_upper'].tail(4).values
                
                # Plot forecast line
                ax.plot(forecast_x, forecast_y, '--', linewidth=2, 
                       color='red', label='Forecast')
                
                # Plot confidence interval
                ax.fill_between(forecast_x, forecast_lower, forecast_upper, 
                               alpha=0.3, color='red', label='Confidence Interval')
                
                # Add forecast date labels
                forecast_dates = ['F+1', 'F+2', 'F+3', 'F+4']
                all_x = list(historical_x) + list(forecast_x)
                all_labels = date_labels + forecast_dates
                
                # Use post-intro data for meaningful statistics
                if trim_idx > 0:
                    post_intro_data = weekday_data[trim_idx:]
                    avg_qty = np.mean(post_intro_data) if len(post_intro_data) > 0 else np.mean(weekday_data)
                    max_qty = np.max(post_intro_data) if len(post_intro_data) > 0 else np.max(weekday_data)
                else:
                    avg_qty = np.mean(weekday_data)
                    max_qty = np.max(weekday_data)
            else:
                # No forecast available - use all historical data
                all_x = historical_x
                all_labels = date_labels
                avg_qty = np.mean(weekday_data)
                max_qty = np.max(weekday_data)
            
            ax.set_title(f'{weekday}', fontweight='bold')
            ax.set_ylabel('Quantity Sold')
            ax.set_xlabel('Date')
            ax.grid(True, alpha=0.3)
            
            # Set x-axis labels
            ax.set_xticks(all_x)
            ax.set_xticklabels(all_labels, rotation=45, ha='right')
            
            # Set y-axis to start at 0
            ax.set_ylim(bottom=0)
            
            # Add statistics text
            stats_text = f'Avg: {avg_qty:.1f}\nMax: {max_qty:.0f}'
            
            if forecast is not None:
                next_forecast = forecast['yhat'].tail(1).values[0]
                stats_text += f'\nNext: {next_forecast:.1f}'
            
            ax.text(0.02, 0.98, stats_text, 
                   transform=ax.transAxes, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Add legend only to first subplot
            if i == 0:
                ax.legend(loc='upper right', fontsize=8)
        
        plt.tight_layout()
        
        # Save plot with sanitized filename
        safe_filename = re.sub(r'[^\w\s-]', '', item_name).replace(' ', '_')
        filepath = f'../reports/grid_plots/{safe_filename}_grid_plot.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
    
    print(f"Grid plots with forecasting saved to ../reports/grid_plots/")




def main():
    """Main grid plot workflow"""
    print("SHECHILL PATISSERIE GRID PLOT REPORTS")
    print("=" * 40)
    
    # Setup
    ensure_directories()
    
    # Load and parse data
    df = load_quantity_data()
    _, weekday_columns = parse_date_columns(df)
    
    # Generate grid plots
    create_grid_plots(df, weekday_columns)
    
    # Print final summary
    print(f"\n=== GRID PLOT SUMMARY ===")
    print(f"Grid Plots Generated: {len(df)} items")
    
    print("\nGrid plot reports complete! Check the ../reports/grid_plots/ directory for outputs.")

if __name__ == "__main__":
    main()
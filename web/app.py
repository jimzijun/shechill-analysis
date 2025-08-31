"""
Shechill Patisserie Forecasting Dashboard
========================================

A dynamic web interface for viewing sales forecasting plots.
Generates plots on-demand using Prophet forecasting for bakery inventory planning.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, render_template, jsonify, make_response, request, session, redirect, url_for, flash
import pandas as pd
import secrets
from functools import wraps

# Import our custom modules  
from src.analysis.forecast_manager import ForecastManager
from plot_renderer import render_item_plot

# Initialize forecast manager with correct path
forecast_manager = ForecastManager(forecast_dir="../data/forecasts")

app = Flask(__name__)

# Configure Flask session
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_urlsafe(32))

# Get webapp password from environment
WEBAPP_PASSWORD = os.environ.get('WEBAPP_PASSWORD', 'shechill2025')

def is_authenticated():
    """Check if user is authenticated"""
    return session.get('authenticated', False)

def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_available_items():
    """Get list of available items from forecast data"""
    forecasts = forecast_manager.get_available_forecasts()
    
    items = []
    for forecast_info in forecasts:
        item_name = forecast_info['item_name']
        items.append({
            'item_name': item_name,
            'slug': _create_item_slug(item_name),
            'generated_at': forecast_info['generated_at'],
            'filename': forecast_info['filename']
        })
    
    return items

def _create_item_slug(item_name: str) -> str:
    """Create URL-safe slug from item name"""
    import re
    slug = re.sub(r'[^\w\s-]', '', item_name).replace(' ', '_').lower()
    return slug

def _load_historical_quantity_data() -> dict:
    """Load historical quantity data from CSV for plot rendering"""
    try:
        csv_path = '../data/quantity_per_day_per_item.csv'
        if not os.path.exists(csv_path):
            return {}
        
        df = pd.read_csv(csv_path)
        
        # Parse dates and group by weekday
        quantity_data = {}
        weekday_data = {'Tuesday': [], 'Wednesday': [], 'Thursday': [], 
                       'Friday': [], 'Saturday': [], 'Sunday': []}
        
        # Parse each date row
        for idx, row in df.iterrows():
            date_formatted = row['Date']
            # Parse "07/01 - Tuesday" format
            import re
            match = re.match(r'(\d+/\d+) - (\w+)', date_formatted)
            if match:
                date_str, weekday = match.groups()
                if weekday in weekday_data:
                    weekday_data[weekday].append({
                        'index': idx,
                        'date_str': date_str,
                        'date_formatted': date_formatted
                    })
        
        # Get item columns (exclude Date)
        item_columns = [col for col in df.columns if col != 'Date']
        
        # Build quantity data for each item
        for item_name in item_columns:
            item_data = {}
            
            for weekday, date_info_list in weekday_data.items():
                dates = []
                quantities = []
                date_labels = []
                
                for date_info in date_info_list:
                    idx = date_info['index']
                    quantity = df.iloc[idx][item_name] if item_name in df.columns else 0
                    quantities.append(quantity)
                    dates.append(date_info['date_formatted'])
                    date_labels.append(date_info['date_str'])
                
                item_data[weekday] = {
                    'dates': dates,
                    'quantities': quantities,
                    'date_labels': date_labels
                }
            
            quantity_data[item_name] = item_data
        
        return quantity_data
        
    except Exception as e:
        print(f"❌ Error loading quantity data: {e}")
        return {}

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - password only"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == WEBAPP_PASSWORD:
            session['authenticated'] = True
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Incorrect password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout - clear session"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Main dashboard page"""
    items = get_available_items()
    return render_template('index.html', items=items, total_items=len(items))

@app.route('/plot/<item_slug>')
@login_required
def serve_dynamic_plot(item_slug):
    """Generate and serve plot dynamically"""
    # Find item by slug
    items = get_available_items()
    item_name = None
    
    for item in items:
        if item['slug'] == item_slug:
            item_name = item['item_name']
            break
    
    if not item_name:
        return "Item not found", 404
    
    try:
        # Load forecast data
        forecast_data = forecast_manager.load_item_forecast(item_name)
        
        if not forecast_data:
            return "Forecast data not found", 404
        
        # Load historical quantity data
        quantity_data_all = _load_historical_quantity_data()
        quantity_data = quantity_data_all.get(item_name, {})
        
        # Get plot type from query parameter
        plot_type = request.args.get('type', 'grid')
        
        # Render plot
        plot_base64 = render_item_plot(item_name, forecast_data, quantity_data, plot_type)
        
        if not plot_base64:
            return "Error generating plot", 500
        
        # Return HTML with embedded image
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{item_name} - Forecast Plot</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                html, body {{ height: 100%; }}
                body {{ 
                    font-family: Arial, sans-serif; 
                    display: grid;
                    place-items: center;
                    background: white;
                }}
                .plot-container {{ 
                    width: 100%;
                    height: 100%;
                    display: grid;
                    place-items: center;
                }}
                .plot-image {{ 
                    max-width: 100%; 
                    max-height: 100%;
                    width: auto;
                    height: auto;
                    object-fit: contain;
                }}
            </style>
        </head>
        <body>
            <div class="plot-container">
                <img src="data:image/png;base64,{plot_base64}" alt="{item_name} forecast plot" class="plot-image">
            </div>
        </body>
        </html>
        """
        
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        print(f"❌ Error serving plot for {item_name}: {e}")
        return f"Error generating plot: {str(e)}", 500

@app.route('/api/items')
@login_required
def api_items():
    """API endpoint for item data"""
    items = get_available_items()
    return jsonify(items)

@app.route('/api/plot/<item_slug>')
@login_required
def api_plot(item_slug):
    """API endpoint for plot image as base64"""
    # Find item by slug
    items = get_available_items()
    item_name = None
    
    for item in items:
        if item['slug'] == item_slug:
            item_name = item['item_name']
            break
    
    if not item_name:
        return jsonify({'error': 'Item not found'}), 404
    
    try:
        # Load forecast data
        forecast_data = forecast_manager.load_item_forecast(item_name)
        
        if not forecast_data:
            return jsonify({'error': 'Forecast data not found'}), 404
        
        # Load historical quantity data
        quantity_data_all = _load_historical_quantity_data()
        quantity_data = quantity_data_all.get(item_name, {})
        
        # Get plot type from query parameter
        plot_type = request.args.get('type', 'grid')
        
        # Render plot
        plot_base64 = render_item_plot(item_name, forecast_data, quantity_data, plot_type)
        
        if not plot_base64:
            return jsonify({'error': 'Error generating plot'}), 500
        
        return jsonify({
            'item_name': item_name,
            'plot_type': plot_type,
            'image': plot_base64,
            'format': 'png'
        })
        
    except Exception as e:
        print(f"❌ Error serving plot API for {item_name}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/forecast-summaries')
@login_required
def api_forecast_summaries():
    """API endpoint for dashboard card forecast summaries"""
    try:
        items = get_available_items()
        summaries = []
        
        for item in items:
            item_name = item['item_name']
            
            # Load forecast data
            forecast_data = forecast_manager.load_item_forecast(item_name)
            
            if forecast_data:
                # Get weekday breakdown for historical averages
                weekday_breakdown = forecast_data.get('weekday_breakdown', {})
                
                # Calculate average daily sales from historical data
                total_qty = 0
                total_days = 0
                for weekday_data in weekday_breakdown.values():
                    if weekday_data and 'quantities' in weekday_data:
                        quantities = weekday_data['quantities']
                        total_qty += sum(quantities)
                        total_days += len(quantities)
                
                avg_daily_sales = round(total_qty / total_days, 1) if total_days > 0 else 0
                
                # Get forecast trend from forecast DataFrame
                forecast_df = forecast_data.get('forecast_df')
                trend_direction = 'stable'
                confidence_score = 0.5
                next_week_forecast = 0
                
                if forecast_df is not None:
                    # Get future forecast values (next 7 days)
                    from datetime import date
                    today = date.today()
                    
                    future_forecasts = []
                    for _, row in forecast_df.iterrows():
                        forecast_date = pd.to_datetime(row['ds']).date()
                        if forecast_date > today:
                            yhat = float(row.get('yhat', 0))
                            if yhat > 0:  # Only include positive forecasts
                                future_forecasts.append(yhat)
                        if len(future_forecasts) >= 7:  # Get next 7 days
                            break
                    
                    if future_forecasts:
                        next_week_forecast = round(sum(future_forecasts), 1)
                        
                        # Simple trend calculation: compare future avg to historical avg
                        future_avg = sum(future_forecasts) / len(future_forecasts)
                        if future_avg > avg_daily_sales * 1.1:  # 10% threshold
                            trend_direction = 'up'
                        elif future_avg < avg_daily_sales * 0.9:
                            trend_direction = 'down'
                        
                        # Simple confidence based on prediction interval width
                        if len(forecast_df) > 0:
                            sample_row = forecast_df.iloc[0]
                            yhat = float(sample_row.get('yhat', 1))
                            yhat_lower = float(sample_row.get('yhat_lower', 0))
                            yhat_upper = float(sample_row.get('yhat_upper', 2))
                            
                            if yhat > 0:
                                interval_width = (yhat_upper - yhat_lower) / yhat
                                confidence_score = max(0.1, min(0.9, 1 - (interval_width / 2)))
                            
                summaries.append({
                    'item_name': item_name,
                    'slug': item['slug'],
                    'avg_daily_sales': avg_daily_sales,
                    'trend_direction': trend_direction,
                    'confidence_score': round(confidence_score, 2),
                    'next_week_forecast': next_week_forecast,
                    'generated_at': item.get('generated_at', '')
                })
            else:
                # Fallback for items without forecast data
                summaries.append({
                    'item_name': item_name,
                    'slug': item['slug'],
                    'avg_daily_sales': 0,
                    'trend_direction': 'stable',
                    'confidence_score': 0,
                    'next_week_forecast': 0,
                    'generated_at': item.get('generated_at', '')
                })
        
        return jsonify({
            'summaries': summaries,
            'total_items': len(summaries)
        })
        
    except Exception as e:
        print(f"❌ Error generating forecast summaries: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/forecast/<item_slug>')
@login_required
def api_forecast_data(item_slug):
    """API endpoint for forecast datatable data"""
    # Find item by slug
    items = get_available_items()
    item_name = None
    
    for item in items:
        if item['slug'] == item_slug:
            item_name = item['item_name']
            break
    
    if not item_name:
        return jsonify({'error': 'Item not found'}), 404
    
    try:
        # Load forecast data
        forecast_data = forecast_manager.load_item_forecast(item_name)
        
        if not forecast_data:
            return jsonify({'error': 'Forecast data not found'}), 404
        
        # Extract forecast DataFrame
        forecast_df = forecast_data.get('forecast_df')
        if forecast_df is None:
            return jsonify({'error': 'Forecast DataFrame not found'}), 404
        
        # Prepare calendar format data grouped by weeks
        from datetime import date
        today = date.today()
        
        weeks_data = {}
        weekday_names = ['Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for _, row in forecast_df.iterrows():
            date_obj = pd.to_datetime(row['ds'])
            
            # Skip Monday (weekday 0)
            if date_obj.weekday() == 0:
                continue
            
            # Get ISO week number and year
            year, week_num, _ = date_obj.isocalendar()
            week_key = f"{year}-W{week_num:02d}"
            
            # Calculate Monday of this week for display
            days_since_monday = date_obj.weekday()
            week_start = date_obj - pd.Timedelta(days=days_since_monday)
            week_display = week_start.strftime('%m/%d')
            
            # Initialize week if not exists
            if week_key not in weeks_data:
                weeks_data[week_key] = {
                    'week_label': week_display,
                    'days': {}
                }
            
            # Get weekday name
            weekday_name = date_obj.strftime('%A')
            
            # Extract forecast values
            yhat = round(float(row.get('yhat', 0)), 1)
            yhat_lower_raw = float(row.get('yhat_lower', 0))
            yhat_upper_raw = float(row.get('yhat_upper', 0))
            
            # Display raw values without max logic
            lower_bound = round(yhat_lower_raw, 1)
            upper_bound = round(yhat_upper_raw, 1)
            
            # Determine date status (past, today, future)
            forecast_date = date_obj.date()
            if forecast_date < today:
                date_status = 'past'
            elif forecast_date == today:
                date_status = 'today'
            else:
                date_status = 'future'
            
            weeks_data[week_key]['days'][weekday_name] = {
                'date': date_obj.strftime('%m/%d'),
                'forecast': yhat,
                'lower': lower_bound,
                'upper': upper_bound,
                'yhat': yhat,
                'status': date_status
            }
        
        # Convert to sorted list
        weeks_list = []
        for week_key in sorted(weeks_data.keys()):
            week_data = weeks_data[week_key]
            # Ensure all weekdays are present with empty values if missing
            for day in weekday_names:
                if day not in week_data['days']:
                    week_data['days'][day] = None
            weeks_list.append(week_data)
        
        return jsonify({
            'item_name': item_name,
            'weeks': weeks_list,
            'total_weeks': len(weeks_list)
        })
        
    except Exception as e:
        print(f"❌ Error serving forecast data for {item_name}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/item/<item_slug>')
@login_required
def item_detail(item_slug):
    """Individual item detail page with dynamic plot"""
    items = get_available_items()
    
    # Find the matching item
    item_info = None
    for item in items:
        if item['slug'] == item_slug:
            item_info = item
            break
    
    if not item_info:
        return "Item not found", 404
    
    return render_template('item_detail.html', item=item_info, plot_url=f'/plot/{item_slug}')

if __name__ == '__main__':
    # Get host and port from environment or use defaults
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', '8000'))
    
    print("Shechill Patisserie Dynamic Forecasting Dashboard")
    print("=" * 50)
    print("🚀 Starting web server with on-demand plot generation...")
    print(f"📊 Open http://localhost:{port} in your browser")
    print("⚡ Plots are now generated dynamically - no pre-rendering needed!")
    print("Press Ctrl+C to stop the server")
    
    app.run(debug=True, host=host, port=port)
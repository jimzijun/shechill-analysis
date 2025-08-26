"""
Shechill Patisserie Forecasting Dashboard
========================================

A minimalistic web interface for viewing sales forecasting plots.
Displays grid plots with Prophet forecasting for bakery inventory planning.
"""

from flask import Flask, render_template, send_file, jsonify, make_response
import os
import glob
from pathlib import Path

app = Flask(__name__)

def get_available_plots():
    """Get list of available plot files"""
    plot_dir = '../reports/grid_plots'
    if not os.path.exists(plot_dir):
        return []
    
    plot_files = glob.glob(os.path.join(plot_dir, '*.png'))
    plots = []
    
    for file_path in plot_files:
        filename = os.path.basename(file_path)
        # Extract item name from filename (remove _grid_plot.png)
        item_name = filename.replace('_grid_plot.png', '').replace('_', ' ')
        plots.append({
            'filename': filename,
            'item_name': item_name,
            'path': file_path
        })
    
    # Sort alphabetically by item name
    plots.sort(key=lambda x: x['item_name'])
    return plots

@app.route('/')
def index():
    """Main dashboard page"""
    plots = get_available_plots()
    return render_template('index.html', plots=plots, total_items=len(plots))

@app.route('/plot/<filename>')
def serve_plot(filename):
    """Serve individual plot image"""
    plot_path = os.path.join('../reports/grid_plots', filename)
    if os.path.exists(plot_path):
        response = make_response(send_file(plot_path, mimetype='image/png'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    else:
        return "Plot not found", 404

@app.route('/api/plots')
def api_plots():
    """API endpoint for plot data"""
    plots = get_available_plots()
    return jsonify(plots)

@app.route('/item/<item_slug>')
def item_detail(item_slug):
    """Individual item detail page"""
    plots = get_available_plots()
    
    # Find the matching plot
    item_plot = None
    for plot in plots:
        if plot['item_name'].lower().replace(' ', '_') == item_slug.lower():
            item_plot = plot
            break
    
    if not item_plot:
        return "Item not found", 404
    
    return render_template('item_detail.html', plot=item_plot)

if __name__ == '__main__':
    # Get host and port from environment or use defaults
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', '8000'))
    
    print("Shechill Patisserie Forecasting Dashboard")
    print("=" * 45)
    print("Starting web server...")
    print(f"Open http://localhost:{port} in your browser")
    print("Press Ctrl+C to stop the server")
    
    app.run(debug=True, host=host, port=port)
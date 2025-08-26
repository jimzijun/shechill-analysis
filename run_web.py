#!/usr/bin/env python3
"""
Shechill Patisserie Web Dashboard Runner
=======================================

This script starts the web dashboard for viewing forecasting plots.

Usage:
    python run_web.py [--port PORT] [--host HOST]
    
Options:
    --port PORT    Port to run the server on (default: 8000)
    --host HOST    Host to bind to (default: 127.0.0.1)
    --public       Make server accessible from other machines (0.0.0.0)
"""

import sys
import os
import subprocess
import argparse

def check_plots_exist():
    """Check if forecasting plots exist"""
    plot_dir = 'reports/grid_plots'
    if not os.path.exists(plot_dir):
        return False
    
    import glob
    plots = glob.glob(os.path.join(plot_dir, '*.png'))
    return len(plots) > 0

def main():
    parser = argparse.ArgumentParser(description='Start Shechill Patisserie web dashboard')
    parser.add_argument('--port', type=int, default=8000, help='Port to run server on')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--public', action='store_true', help='Make server accessible from other machines')
    
    args = parser.parse_args()
    
    # Check if plots exist
    if not check_plots_exist():
        print("⚠️  WARNING: No forecasting plots found!")
        print("Run the analysis first: python run_analysis.py")
        print("\nContinuing anyway - you can generate plots later...")
        print()
    
    # Set host
    host = '0.0.0.0' if args.public else args.host
    
    print("=" * 50)
    print("SHECHILL PATISSERIE WEB DASHBOARD")
    print("=" * 50)
    print(f"Starting web server...")
    print(f"Host: {host}")
    print(f"Port: {args.port}")
    
    if args.public:
        print("🌐 Server accessible from other machines")
    
    print(f"\n🚀 Open http://localhost:{args.port} in your browser")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Set environment variables for Flask
    env = os.environ.copy()
    env['FLASK_HOST'] = host
    env['FLASK_PORT'] = str(args.port)
    
    # Change to web directory and run Flask app
    os.chdir('web')
    
    try:
        # Run the Flask app with custom host/port
        subprocess.run([
            sys.executable, 'app.py'
        ], env=env)
    except KeyboardInterrupt:
        print("\n\nShutting down web server...")
        print("👋 Thanks for using Shechill Patisserie Dashboard!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
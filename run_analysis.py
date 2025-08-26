#!/usr/bin/env python3
"""
Shechill Patisserie Analysis Runner
=================================

This script runs the complete analysis pipeline:
1. Quantity analysis (data processing)
2. Visualization generation (forecasting plots)

Usage:
    python run_analysis.py [--quantity-only] [--viz-only]
    
Options:
    --quantity-only    Run only quantity analysis
    --viz-only        Run only visualization generation
"""

import sys
import os
import subprocess
import argparse

def run_quantity_analysis():
    """Run the quantity analysis script"""
    print("=" * 50)
    print("RUNNING QUANTITY ANALYSIS")
    print("=" * 50)
    
    # Run script in analysis directory
    result = subprocess.run([sys.executable, 'quantity_analysis.py'], cwd='analysis', capture_output=False)
    
    return result.returncode == 0

def run_visualization():
    """Run the visualization script"""
    print("\n" + "=" * 50)
    print("RUNNING VISUALIZATION GENERATION")
    print("=" * 50)
    
    # Run script in analysis directory
    result = subprocess.run([sys.executable, 'visualization_reports.py'], cwd='analysis', capture_output=False)
    
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description='Run Shechill Patisserie analysis pipeline')
    parser.add_argument('--quantity-only', action='store_true', help='Run only quantity analysis')
    parser.add_argument('--viz-only', action='store_true', help='Run only visualization generation')
    
    args = parser.parse_args()
    
    success = True
    
    if args.viz_only:
        success = run_visualization()
    elif args.quantity_only:
        success = run_quantity_analysis()
    else:
        # Run both
        success = run_quantity_analysis()
        if success:
            success = run_visualization()
    
    if success:
        print("\n" + "=" * 50)
        print("ANALYSIS COMPLETE!")
        print("=" * 50)
        print("✅ Data processing completed successfully")
        print("✅ Forecasting plots generated")
        print("\nNext steps:")
        print("  1. Start the web dashboard: python run_web.py")
        print("  2. Open http://localhost:8000 in your browser")
    else:
        print("\n" + "=" * 50)
        print("ANALYSIS FAILED!")
        print("=" * 50)
        print("❌ Check the error messages above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
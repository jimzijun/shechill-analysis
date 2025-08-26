#!/usr/bin/env python3
"""
Square Sales Quantity Fetcher
============================

Fetches item sales quantities from Square Orders API for Shechill Patisserie.
Returns data in the same format as your existing CSV files.

Usage:
    export SQUARE_ACCESS_TOKEN="your_token_here"
    python square_sales_fetcher.py --days 30

Features:
- Fetches orders with line items (quantities sold per item)
- Filters by date range  
- Processes into daily sales summary
- Exports CSV compatible with existing analysis pipeline
- Handles pagination for large datasets
"""

import os
import sys
import csv
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any

try:
    from square import Square
    from square.environment import SquareEnvironment
except ImportError:
    print("❌ Square SDK not installed. Install with: pip install squareup")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # dotenv not installed, continue without it

class SquareSalesFetcher:
    """Fetches sales quantity data from Square Orders API"""
    
    def __init__(self, access_token: str):
        """Initialize Square client"""
        self.client = Square(
            token=access_token,
            environment=SquareEnvironment.PRODUCTION  # Using production environment
        )
        
        # Get locations
        self.locations = self._get_locations()
        if not self.locations:
            raise ValueError("No locations found")
            
        print(f"✅ Connected to Square API")
        print(f"📍 Found {len(self.locations)} location(s):")
        for loc in self.locations:
            print(f"   - {loc.get('name', 'Unknown')} ({loc.get('id')})")
    
    def _get_locations(self) -> List[Dict[str, Any]]:
        """Get all locations"""
        try:
            locations_response = self.client.locations.list()
            # The response directly contains the locations list
            locations = getattr(locations_response, 'locations', [])
            return [{'id': loc.id, 'name': loc.name} for loc in locations]
        except Exception as e:
            print(f"❌ Error getting locations: {e}")
            return []
    
    def fetch_sales_data(self, start_date: datetime, end_date: datetime, 
                        location_id: str = None) -> Dict[str, Dict[str, float]]:
        """
        Fetch sales quantities from Square Orders API
        Returns: {item_name: {date: quantity}}
        """
        print(f"📥 Fetching sales data from {start_date.date()} to {end_date.date()}")
        
        if not location_id and self.locations:
            location_id = self.locations[0]['id']
            print(f"📍 Using location: {location_id}")
        
        sales_data = defaultdict(lambda: defaultdict(float))
        cursor = None
        page = 1
        total_orders = 0
        
        try:
            while True:
                print(f"   📄 Fetching page {page}...")
                
                # Prepare search request
                query_params = {
                    "filter": {
                        "date_time_filter": {
                            "created_at": {
                                "start_at": start_date.isoformat() + 'Z',
                                "end_at": end_date.isoformat() + 'Z'
                            }
                        }
                    }
                }
                
                result = self.client.orders.search(
                    location_ids=[location_id],
                    query=query_params,
                    limit=100,
                    cursor=cursor
                )
                
                # Process the response directly
                orders = getattr(result, 'orders', []) or []
                total_orders += len(orders)
                
                # Process each order
                for order in orders:
                    self._process_order(order, sales_data)
                
                # Check for more pages
                cursor = getattr(result, 'cursor', None)
                if not cursor:
                    break
                page += 1
                    
        except Exception as e:
            print(f"❌ Exception while fetching: {e}")
        
        print(f"✅ Processed {total_orders} orders")
        return dict(sales_data)
    
    def _process_order(self, order: Any, sales_data: Dict):
        """Process individual order and extract line item quantities"""
        try:
            # Get order date
            created_at = getattr(order, 'created_at', None)
            if not created_at:
                return
                
            # Parse date
            order_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            date_key = order_date.strftime('%m/%d - %A')  # Format: "8/22 - Thursday"
            
            # Process line items
            line_items = getattr(order, 'line_items', [])
            if not line_items:
                return
                
            for item in line_items:
                # Handle None values safely
                item_name = getattr(item, 'name', None)
                if not item_name:
                    continue
                item_name = str(item_name).strip()
                
                quantity_str = getattr(item, 'quantity', '0')
                if quantity_str is None:
                    quantity_str = '0'
                
                try:
                    quantity = float(quantity_str)
                    if quantity > 0:
                        sales_data[item_name][date_key] += quantity
                except (ValueError, TypeError):
                    continue
                    
        except Exception as e:
            print(f"⚠️  Error processing order: {e}")
    
    def export_to_csv(self, sales_data: Dict[str, Dict[str, float]], output_path: str):
        """Export sales data to CSV matching existing format"""
        print(f"💾 Exporting to {output_path}")
        
        if not sales_data:
            print("⚠️  No sales data to export")
            return
        
        # Get all unique dates across all items
        all_dates = set()
        for item_dates in sales_data.values():
            all_dates.update(item_dates.keys())
        
        # Sort dates chronologically
        def sort_date_key(date_str):
            try:
                date_part = date_str.split(' - ')[0]  # Get "8/22" part
                month, day = map(int, date_part.split('/'))
                # Assume current year for sorting
                return datetime(datetime.now().year, month, day)
            except:
                return datetime.min
        
        sorted_dates = sorted(all_dates, key=sort_date_key)
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Item'] + sorted_dates
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Sort items alphabetically
            for item_name in sorted(sales_data.keys()):
                row = {'Item': item_name}
                for date in sorted_dates:
                    row[date] = sales_data[item_name].get(date, 0.0)
                writer.writerow(row)
        
        print(f"✅ Exported {len(sales_data)} items across {len(sorted_dates)} dates")
    
    def print_summary(self, sales_data: Dict[str, Dict[str, float]]):
        """Print summary of fetched data"""
        if not sales_data:
            print("📊 No sales data found")
            return
            
        total_items = len(sales_data)
        total_dates = len(set(date for dates in sales_data.values() for date in dates))
        total_quantity = sum(sum(dates.values()) for dates in sales_data.values())
        
        print("\n📊 SALES SUMMARY")
        print(f"   Items: {total_items}")
        print(f"   Date range: {total_dates} unique dates")
        print(f"   Total quantity sold: {total_quantity:,.0f}")
        
        # Top 5 items by total quantity
        top_items = sorted(
            [(item, sum(dates.values())) for item, dates in sales_data.items()],
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        print("\n🔥 TOP 5 ITEMS:")
        for i, (item, qty) in enumerate(top_items, 1):
            print(f"   {i}. {item}: {qty:,.0f} sold")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Fetch Square sales quantity data')
    parser.add_argument('--days', type=int, default=7, 
                       help='Number of days to fetch (default: 7)')
    parser.add_argument('--output', default='square_sales_data.csv',
                       help='Output CSV file (default: square_sales_data.csv)')
    parser.add_argument('--location-id', 
                       help='Specific Square location ID (optional)')
    
    args = parser.parse_args()
    
    # Check for access token
    access_token = os.environ.get('SQUARE_ACCESS_TOKEN')
    if not access_token:
        print("❌ SQUARE_ACCESS_TOKEN not found")
        print("   Option 1: Set environment variable:")
        print("   export SQUARE_ACCESS_TOKEN='your_token_here'")
        print("")
        print("   Option 2: Create .env file with:")
        print("   SQUARE_ACCESS_TOKEN=your_token_here")
        print("")
        print("   Get your token from https://developer.squareup.com/")
        sys.exit(1)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    print("=" * 60)
    print("SQUARE SALES QUANTITY FETCHER")
    print("=" * 60)
    print(f"📅 Date range: {start_date.date()} to {end_date.date()}")
    print(f"📁 Output file: {args.output}")
    
    try:
        # Initialize fetcher
        fetcher = SquareSalesFetcher(access_token)
        
        # Fetch sales data
        sales_data = fetcher.fetch_sales_data(start_date, end_date, args.location_id)
        
        if not sales_data:
            print("⚠️  No sales data found for the specified date range")
            return
        
        # Export to CSV
        fetcher.export_to_csv(sales_data, args.output)
        
        # Print summary
        fetcher.print_summary(sales_data)
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Sales data exported to CSV")
        print(f"📁 File: {args.output}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
# Shechill Patisserie Forecasting System

A comprehensive sales analysis and forecasting system for Shechill Patisserie, featuring Prophet-based forecasting and a minimalistic web dashboard.

## 📁 Directory Structure

```
shechill-analysis/
├── analysis/                   # Data processing and analysis scripts
│   ├── quantity_analysis.py    # Transaction data processing
│   └── visualization_reports.py # Prophet forecasting plots generation
├── web/                        # Web dashboard application  
│   ├── app.py                  # Flask web application
│   └── templates/              # HTML templates
│       ├── base.html
│       ├── index.html
│       └── item_detail.html
├── data/                       # Data files (input and processed)
│   ├── transaction-summary.csv # Raw transaction data
│   └── quantity_per_day_per_item.csv # Processed quantity data
├── reports/                    # Generated visualizations
│   └── grid_plots/            # Forecasting plot images
├── run_analysis.py            # Analysis pipeline runner
└── run_web.py                 # Web dashboard runner
```

## 🚀 Quick Start

### 1. Run Analysis Pipeline
```bash
# Run complete analysis (data processing + visualization)
python run_analysis.py

# Or run components separately
python run_analysis.py --quantity-only    # Data processing only
python run_analysis.py --viz-only         # Visualization only
```

### 2. Start Web Dashboard
```bash
# Start web server (default: localhost:8000)
python run_web.py

# Custom port/host
python run_web.py --port 9000 --host 0.0.0.0

# Make accessible from other machines
python run_web.py --public
```

### 3. View Results
- Open `http://localhost:8000` in your browser
- Browse 85+ forecasting plots with Prophet predictions
- Search items, view detailed analysis, download plots

## 📊 Features

### Analysis Pipeline
- **Smart Data Processing**: Filters categories (Croissant, Bread, Pastries, Drink)
- **Data Cleaning**: Merges duplicate items, removes seasonal specials
- **Prophet Forecasting**: Time series forecasting with confidence intervals
- **Smart Zero Handling**: Ignores pre-introduction periods (4+ consecutive zeros)

### Web Dashboard
- **Minimalistic Design**: Clean, professional interface
- **Search & Filter**: Find items quickly
- **Grid/List Views**: Flexible viewing options
- **Full-Screen Viewing**: Modal zoom and download options
- **Mobile Responsive**: Works on all devices

## 📈 Prophet Forecasting

Each plot shows:
- **Blue line**: Historical sales data with actual dates (M/D format)
- **Red dashed line**: Prophet forecasting predictions
- **Red shaded area**: 80% confidence intervals
- **Statistics**: Average, maximum, and next forecast values

## 🛠 Technical Details

### Requirements
- Python 3.8+
- pandas, matplotlib, seaborn
- prophet (Facebook Prophet)
- flask (web dashboard)

### Data Flow
1. **Raw Data**: `transaction-summary.csv` with Date, Item, Category, Qty
2. **Processing**: Category filtering, item cleaning, Monday exclusion
3. **Forecasting**: Prophet models per item/weekday with smart zero handling
4. **Visualization**: 6-panel weekday grid plots with forecasting
5. **Web Interface**: Flask dashboard for plot viewing and analysis

### Business Logic
- **Excludes Mondays**: Bakery closed
- **Filters Categories**: Only core bakery items
- **Removes Seasonal Items**: 4th of July, Easter specials
- **Consolidates Items**: Merges weekend variants and duplicates
- **Smart Forecasting**: Uses only post-introduction data

## 📅 Usage Workflow

1. **Update Data**: Replace `data/transaction-summary.csv` with new data
2. **Run Analysis**: `python run_analysis.py` to process and generate plots
3. **Start Dashboard**: `python run_web.py` to view results
4. **Plan Inventory**: Use forecasting data for next week's preparation

## 🎯 Output Files

- **Data**: `data/quantity_per_day_per_item.csv` (85 items × 146 dates)
- **Plots**: `reports/grid_plots/` (85 PNG files with forecasting)
- **Web Access**: Local dashboard at `http://localhost:8000`

---

**🥐 Built for Shechill Patisserie | Powered by Prophet Forecasting**
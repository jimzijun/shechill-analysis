# Shechill Patisserie Forecasting System

A comprehensive sales analysis and forecasting system for Shechill Patisserie, featuring Prophet-based forecasting and a minimalistic web dashboard.

## 📁 Project Structure

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed directory layout and file descriptions.

## 🚀 Quick Start

### 1. Run Analysis Pipeline
```bash
# Run complete data pipeline (Square API → processing → forecasting)
python -m src.data_pipeline.data_update_manager

# Or run analysis components separately
python -m src.analysis.quantity_analysis      # Data processing only
python -m src.analysis.forecast_generator     # Forecasting only
```

### 2. Start Web Dashboard
```bash
# Start web server with plot caching (default: localhost:8000)
python web/app.py
# Access at http://localhost:8000

# Custom host/port via environment variables
FLASK_HOST=0.0.0.0 FLASK_PORT=9000 python web/app.py
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
- **Multi-Layer Caching**: File-based and in-memory plot caching for performance
- **Smart Cache Management**: Automatic cache invalidation and warmup

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
1. **Square API Integration**: Fetches transaction data, saves as daily JSON files
2. **Data Processing**: Raw JSON → analysis-ready CSV (category filtering, item cleaning, Monday exclusion)
3. **Prophet Forecasting**: Time series models per item with smart zero handling
4. **Visualization**: Dynamic plot generation with multi-layer caching
5. **Web Dashboard**: Flask app with plot caching, search, and forecast viewing

### Business Logic
- **Excludes Mondays**: Bakery closed
- **Filters Categories**: Only core bakery items
- **Removes Seasonal Items**: 4th of July, Easter specials
- **Consolidates Items**: Merges weekend variants and duplicates
- **Smart Forecasting**: Uses only post-introduction data

## 👥 Development Setup

### Prerequisites
- Python 3.12+
- Git

### Installation
```bash
# Clone the repository
git clone https://github.com/jimzijun/shechill-analysis.git
cd shechill-analysis

# Install dependencies
pip install -e ".[dev]"

# Install git hooks (recommended)
./scripts/install-hooks.sh
```

### Git Hooks
The project includes pre-push hooks that run code quality checks before pushing:
- **Black** formatting check
- **isort** import sorting check  
- **flake8** linting (critical errors)
- **mypy** type checking
- **Smoke test** (import validation)

**Skip hooks** (not recommended): `git push --no-verify`

### Code Quality
Run all checks manually:
```bash
# Format code
black src/ web/
isort src/ web/

# Lint code
flake8 src/ web/

# Type check
mypy src/ web/ --ignore-missing-imports --no-strict-optional
```

## 📅 Usage Workflow

1. **Fetch Data**: `python -m src.square_client.square_api_client` to pull Square API data
2. **Run Pipeline**: `python -m src.data_pipeline.data_update_manager` to process and forecast
3. **Start Dashboard**: `python web/app.py` to view cached results
4. **Background Updates**: `python -m src.data_pipeline.scheduler --daemon` for automated updates
5. **Plan Inventory**: Use forecasting data for next week's preparation

## 🎯 Output Files

- **Raw Transactions**: `data/raw_transactions/` (JSON files by date from Square API)
- **Processed Data**: `data/quantity_per_day_per_item.csv` (analysis-ready format)
- **Forecasts**: `data/forecasts/` (Prophet forecast JSON files per item)
- **Plot Cache**: `data/plot_cache/` (cached plot images for performance)
- **Web Dashboard**: Local dashboard at `http://localhost:8000`

---

**🥐 Built for Shechill Patisserie | Powered by Prophet Forecasting**
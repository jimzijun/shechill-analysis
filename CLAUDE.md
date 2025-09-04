# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- Updated: Testing new release pipeline with PR-based workflow -->

## Commands

### Development Setup
```bash
# Install dependencies with dev tools
pip install -e ".[dev]"

# Install git hooks (runs code quality checks on push)
./scripts/install-hooks.sh
```

### Code Quality
```bash
# Format code
black src/ web/
isort src/ web/

# Lint code  
flake8 src/ web/

# Type check
mypy src/ web/ --ignore-missing-imports --no-strict-optional
```

### Application Commands
```bash
# Run complete data pipeline (Square API → processing → forecasting)
python -m src.data_pipeline.data_update_manager

# Run analysis only (process existing data → generate forecasts)
python -m src.analysis.quantity_analysis
python -m src.analysis.forecast_generator

# Start web dashboard
python web/app.py
# Access at http://localhost:8000

# Pull today's sales data from Square API
python -m src.square_client.square_api_client

# Start background scheduler
python -m src.data_pipeline.scheduler --daemon
```

### Docker
```bash
# Build image
docker build -t shechill-analysis .

# Run with syslog logging (recommended for production)
docker run -d \
  --log-driver syslog \
  --log-opt syslog-address="udp://localhost:514" \
  --name shechill-analysis \
  -e SQUARE_ACCESS_TOKEN=your_token \
  -p 8000:8000 \
  shechill-analysis

# Basic run (development)
docker run -e SQUARE_ACCESS_TOKEN=your_token -p 8000:8000 shechill-analysis
```

## Architecture

### Core System Flow
1. **Square API Integration** (`src/square_client/`) - Fetches transaction data, saves as daily JSON files
2. **Data Pipeline** (`src/data_pipeline/`) - Orchestrates fetch → process → forecast workflow  
3. **Analysis Engine** (`src/analysis/`) - Processes raw JSON → CSV → Prophet forecasts
4. **Web Dashboard** (`web/`) - Flask app with dynamic plot generation and forecast viewing

### Key Components
- `src/config_manager.py` - Centralized configuration management
- `src/data_pipeline/data_update_manager.py` - Main pipeline orchestrator
- `src/analysis/quantity_analysis.py` - Raw data → analysis-ready CSV conversion
- `src/analysis/forecast_generator.py` - Prophet time series forecasting
- `src/analysis/forecast_manager.py` - Forecast data serialization and management
- `web/app.py` - Flask dashboard with search, filtering, and plot viewing
- `web/plot_renderer.py` - Dynamic plot generation from forecast JSON data
- `web/plot_cache.py` - Multi-layer plot caching system for performance

### Data Flow
- Raw transactions stored in `data/raw_transactions/` (JSON files by date)
- Processed data in `data/quantity_per_day_per_item.csv` 
- Forecast data in `data/forecasts/` (Prophet JSON files per item)
- Plot cache in `data/plot_cache/` (file-based and in-memory caching)
- Business logic: Excludes Mondays, filters core bakery categories, smart zero handling

### Configuration
- Environment variables in `.env` file (Square API token, Flask host/port)
- Application config in `config/app_config.json`
- Python 3.11+ required, uses Prophet forecasting library
- Plot caching system with configurable cache sizes and TTL

## Git Hooks
Pre-push hooks automatically run: black, isort, flake8, mypy, and import smoke tests. Skip with `git push --no-verify` (not recommended).
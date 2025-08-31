# Project Structure

## Directory Layout

```
shechill-analysis/
├── src/                    # Source code
│   ├── data_pipeline/      # Data management components
│   │   ├── data_update_manager.py    # Pipeline orchestrator
│   │   ├── scheduler.py              # Background task scheduler
│   │   └── update_pipeline.py        # Pipeline runner script
│   ├── analysis/           # Analysis and forecasting
│   │   ├── quantity_analysis.py      # Process raw data → CSV
│   │   ├── forecast_generator.py     # Generate Prophet forecast data
│   │   ├── forecast_manager.py       # Manage forecast JSON files
│   │   └── run_analysis.py           # Analysis runner script
│   ├── square_client/      # Square API integration
│   │   ├── __init__.py               
│   │   └── square_api_client.py      # Square API client
│   └── config_manager.py   # Configuration management
├── scripts/                # CLI utilities and runners
│   ├── pull_today_sales.py          # Fetch and display today's sales data
│   ├── run_scheduler.py             # Start background scheduler
│   └── run_web.py                   # Start web dashboard
├── web/                    # Web dashboard
│   ├── app.py                       # Flask application
│   ├── plot_renderer.py             # Dynamic plot generation
│   └── templates/                   # HTML templates
│       ├── base.html
│       ├── index.html
│       └── item_detail.html
├── data/                   # Data files
│   ├── raw_transactions/            # JSON files from Square API (ignored by git)
│   ├── forecasts/                   # Prophet forecast JSON files
│   └── quantity_per_day_per_item.csv # Processed analysis data
├── logs/                   # Application logs (ignored by git)
├── config/                 # Configuration files
│   └── app_config.json             # Application configuration
├── terraform/              # Infrastructure as code
│   ├── main.tf                     # Terraform configuration
│   ├── terraform.tfvars            # Variable definitions
│   └── README.md                   # Terraform documentation
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── PROJECT_STRUCTURE.md   # This file
└── README.md              # Project documentation
```

## Usage

### Data Pipeline Commands

```bash
# Fetch and display today's sales data
python scripts/pull_today_sales.py

# Run complete data pipeline (fetch → process → visualize)
python scripts/update_pipeline.py

# Run analysis only (process existing data → visualize)
python scripts/run_analysis.py
```

### Web Dashboard

```bash
# Start the web dashboard
python scripts/run_web.py

# Open http://localhost:8000
```

### Manual Steps

```bash
# Fetch Square data directly (bulk historical fetch)
python src/data_pipeline/square_api_client.py --days 7

# Fetch today's data with summary
python scripts/pull_today_sales.py

# Run analysis directly
cd src/analysis
python quantity_analysis.py
python forecast_generator.py
```

## File Purposes

### Core Components

- **square_api_client.py**: Connects to Square API, fetches transactions, saves as daily JSON files
- **data_update_manager.py**: Orchestrates the complete pipeline (fetch → process → forecast)
- **quantity_analysis.py**: Reads JSON files, processes into analysis-ready CSV format
- **forecast_generator.py**: Generates Prophet forecasting data from CSV and saves as JSON files
- **forecast_manager.py**: Handles loading/saving forecast JSON data with serialization

### Web Dashboard

- **web/app.py**: Flask dashboard with dynamic plot generation and forecast API endpoints
- **plot_renderer.py**: Generates plots on-demand from JSON forecast data

### Infrastructure

- **scheduler.py**: Background task scheduler for automated data updates  
- **config_manager.py**: Manages application configuration and environment settings
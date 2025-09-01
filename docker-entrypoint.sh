#!/bin/bash
set -e

echo "=================================================="
echo "SHECHILL PATISSERIE DOCKER ENTRYPOINT"
echo "=================================================="
echo "Starting Shechill Patisserie system components..."
echo "Time: $(date)"
echo "=================================================="

# Function to handle shutdown gracefully
cleanup() {
    echo ""
    echo "Received shutdown signal. Stopping services..."
    if [ ! -z "$SCHEDULER_PID" ]; then
        echo "Stopping scheduler (PID: $SCHEDULER_PID)..."
        kill $SCHEDULER_PID 2>/dev/null || true
    fi
    if [ ! -z "$WEB_PID" ]; then
        echo "Stopping web dashboard (PID: $WEB_PID)..."
        kill $WEB_PID 2>/dev/null || true
    fi
    echo "Cleanup complete. Goodbye!"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Check if required environment variables are set
if [ -z "$SQUARE_ACCESS_TOKEN" ]; then
    echo "❌ ERROR: SQUARE_ACCESS_TOKEN environment variable is required"
    exit 1
fi

echo "✅ Configuration validated"

# Create necessary directories
mkdir -p data/raw_transactions
mkdir -p data/forecasts
echo "✅ Data directories created"

# Start the web dashboard first (for health checks)
echo ""
echo "🌐 Starting web dashboard..."
export FLASK_HOST=${FLASK_HOST:-0.0.0.0}
export FLASK_PORT=${FLASK_PORT:-8000}

python web/app.py &
WEB_PID=$!

echo "✅ Web dashboard started (PID: $WEB_PID)"

# Wait a moment for web dashboard to initialize
sleep 3

# Initialize the system if needed using built-in --init flag
echo ""
echo "🔧 Checking if system needs initialization..."
python -m src.data_pipeline.data_update_manager --status || {
    echo "🚀 System not initialized. Running initial setup..."
    if ! python -m src.data_pipeline.data_update_manager --init; then
        echo "❌ Initialization failed. Cannot start services without proper setup."
        kill $WEB_PID 2>/dev/null || true
        exit 1
    fi
    echo "✅ System initialized successfully"
}

# Start the scheduler in background directly as module
echo ""
echo "🕒 Starting scheduler..."
python -m src.data_pipeline.scheduler --daemon &
SCHEDULER_PID=$!

echo "✅ Scheduler started (PID: $SCHEDULER_PID)"

echo "✅ Web dashboard started (PID: $WEB_PID)"

echo ""
echo "=================================================="
echo "🚀 SYSTEM READY!"
echo "=================================================="
echo "📊 Web Dashboard: http://localhost:${FLASK_PORT}"
echo "🕒 Scheduler: Running (daily at 22:00)"
echo "📁 Data Directory: /app/data"
echo "=================================================="
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for both processes to complete or be interrupted
wait $SCHEDULER_PID $WEB_PID
#!/bin/bash

# Start Dagster Development Server
# This script launches the Dagster UI for the Binance tick data pipeline

echo "======================================================================"
echo "Starting Dagster UI for Binance Tick Data Pipeline"
echo "======================================================================"
echo ""
echo "Pipeline: dagster_pipeline"
echo "UI will be available at: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "======================================================================"

# Launch Dagster dev server
# Use -m (module) instead of -f (file) to properly load the Dagster definitions
uv run dagster dev -m dagster_pipeline

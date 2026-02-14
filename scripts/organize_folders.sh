#!/bin/bash

# --- Configuration ---
# 1. Define where we are (The Lab)
PROJECT_ROOT="$HOME/SIS_Analysis_WSL"

# 2. Define where the heavy stuff lives (The Warehouse)
# Note: We use the Symlinks we created earlier!
WAREHOUSE_DATA="$PROJECT_ROOT/data"
WAREHOUSE_FIGURES="$PROJECT_ROOT/reports/figures"

echo "Starting Organization..."

# --- Task 1: Move stray CSVs to the Data Warehouse ---
# Only moves files if they exist to avoid errors
if ls *.csv 1> /dev/null 2>&1; then
    echo "📦 Moving stray CSV files to Data Warehouse..."
    mv *.csv "$WAREHOUSE_DATA/"
fi

# --- Task 2: Move stray PNGs to the Figures Warehouse ---
if ls *.png 1> /dev/null 2>&1; then
    echo "🖼️  Moving stray images to Figures Warehouse..."
    mv *.png "$WAREHOUSE_FIGURES/"
fi

echo "✅ Organization complete."
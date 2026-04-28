#!/bin/bash

# Configuration
CONDA_ENV="sis_analysis"
NOTEBOOK_DIR="/home/reyha/SIS_Analysis_WSL/notebooks"

# Notebook paths
NOTEBOOKS=(
    "22_seasonal_variation_do.ipynb"
    "23_seasonal_variation_temp.ipynb"
    "24_seasonal_variation_wtemp.ipynb"
    "25_seasonal_variation_salt.ipynb"
)

# Move to project root
cd "/home/reyha/SIS_Analysis_WSL" || exit

echo "Starting execution of seasonal variation notebooks..."

for NB in "${NOTEBOOKS[@]}"; do
    INPUT_PATH="$NOTEBOOK_DIR/$NB"
    OUTPUT_PATH="${INPUT_PATH%.ipynb}_executed.ipynb" # Save as executed version
    
    echo "------------------------------------------------------------"
    echo "Running: $NB"
    echo "Saving to: $(basename "$OUTPUT_PATH")"
    
    # Run using papermill in the conda environment
    conda run -n "$CONDA_ENV" papermill "$INPUT_PATH" "$OUTPUT_PATH"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully executed $NB"
    else
        echo "❌ Error executing $NB"
    fi
done

echo "------------------------------------------------------------"
echo "All notebooks processed."

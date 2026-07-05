#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- BOILERPLATE INJECTED BY AGENT ---
import os
import sys
import pandas as pd
import logging
from pathlib import Path

CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
import shutil
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
if PROCESSED_DATA_DIR.exists():
    shutil.rmtree(PROCESSED_DATA_DIR, ignore_errors=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')

param_file = CURRENT_SCRIPT.parent / f"step{step_num}_parameter.csv"
PARAMS = {}
if param_file.exists():
    df_params = pd.read_csv(param_file)
    if 'parameter_name' in df_params.columns and 'value' in df_params.columns:
        for _, row in df_params.iterrows():
            PARAMS[row['parameter_name']] = row['value']
# -------------------------------------

from utils.paths import ProjectPaths
from utils.data_loader import load_and_process_data

# Representative months per season and region
tokyo_bay_months = {
    'Spring': 5,   # May
    'Summer': 8,   # August
    'Autumn': 11,  # November
    'Winter': 2    # February
}

default_months = {
    'Spring': 5,   # May
    'Summer': 7,   # July
    'Autumn': 10,  # October
    'Winter': 1    # January
}

layers = {'surface': 1, 'bottom': 2}

def main():
    season = PARAMS.get('season', 'Summer')
    layer_name = PARAMS.get('layer', 'bottom')
    
    # Capitalize appropriately
    season = season.capitalize()
    layer_name = layer_name.lower()
    
    if season not in default_months:
        raise ValueError(f"Invalid season '{season}'. Must be one of {list(default_months.keys())}")
    if layer_name not in layers:
        raise ValueError(f"Invalid layer '{layer_name}'. Must be one of {list(layers.keys())}")
        
    tokyo_rep_month = tokyo_bay_months[season]
    default_rep_month = default_months[season]
    layer_code = layers[layer_name]
    
    print(f"Filtering data for Season: {season} (Tokyo Bay Month: {tokyo_rep_month}, Other Month: {default_rep_month}), Layer: {layer_name} (Code: {layer_code})")
    
    # Load the cleaned, merged dataset
    merged_gdf = load_and_process_data(force_reload=False)
    
    # We do not apply regional filtering here to ensure that Tokyo Bay, Ise Bay,
    # and all divisions remain available downstream in Step 2.
    print(f"Preserving all regions in seasonal subset: {len(merged_gdf)} rows")
            
    # Filter by season, layer, and region-aware representative month
    is_tokyo_bay = merged_gdf['watermass_name'] == 'Tokyo Bay'
    is_correct_month = (
        (is_tokyo_bay & (merged_gdf['surveymont'] == tokyo_rep_month)) |
        (~is_tokyo_bay & (merged_gdf['surveymont'] == default_rep_month))
    )
    
    base_subset = merged_gdf[
        (merged_gdf['season'] == season) &
        (merged_gdf['saisuipoin'] == layer_code) &
        is_correct_month
    ].copy()
    
    min_periods = 15
    parameters_to_process = ['do_', 'temp', 'wtemp', 'salt']
    
    # Ensure backward compatibility directory exists
    legacy_dir = ProjectPaths.ensure_subset_dir(season, layer_name)
    
    for param in parameters_to_process:
        subset = base_subset.copy()
        if param not in subset.columns:
            print(f"Parameter '{param}' not found in data columns. Skipping.")
            continue
            
        subset[param] = pd.to_numeric(subset[param], errors='coerce')
        subset = subset.dropna(subset=[param]).copy()
        
        # Group by station and year, take the mean
        yearly_df = subset.groupby(['zettaicode', 'year'])[param].mean().unstack('year')
        
        # Filter stations with >= min_periods valid years
        yearly_df = yearly_df[yearly_df.notna().sum(axis=1) >= min_periods]
        
        # Zero-pad station index to 8 characters
        yearly_df.index = yearly_df.index.astype(str).str.zfill(8)
        
        param_filename = param.rstrip('_')
        
        # Save to pipeline directory
        out_path = PROCESSED_DATA_DIR / f"yearly_{param_filename}_df.csv"
        yearly_df.to_csv(out_path, index=True)
        
        # Save to legacy/backward compatibility directory
        legacy_path = legacy_dir / f"yearly_{param_filename}_df.csv"
        yearly_df.to_csv(legacy_path, index=True)
        
        print(f"Saved seasonal subset data: {out_path} and {legacy_path} ({yearly_df.shape[0]} stations, {yearly_df.shape[1]} years)")

if __name__ == "__main__":
    main()

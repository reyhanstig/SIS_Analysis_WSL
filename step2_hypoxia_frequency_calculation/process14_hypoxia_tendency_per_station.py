# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- BOILERPLATE INJECTED BY AGENT ---
import os
import pandas as pd
import logging
import matplotlib.pyplot as plt

CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
import shutil
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
if not OUTPUT_DIR.exists():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
if not PROCESSED_DATA_DIR.exists():
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

import argparse
import numpy as np
import seaborn as sns
import yaml
from scipy import stats

from utils.paths import ProjectPaths
from utils.data_loader import load_and_process_data

plt.style.use('../project_style.mplstyle')

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--division', required=True, help="Target division (e.g. 'Tokyo Bay')")
    return parser.parse_args()

def main():
    args = parse_args()
    TARGET_REGION = args.division
    div_clean = TARGET_REGION.replace(' ', '_').lower()

    cwd = Path(os.getcwd())
    if (cwd / 'params.yaml').exists():
        project_root = cwd
    else:
        project_root = cwd.parent
        
    merged_gdf = load_and_process_data(force_reload=False)

    with open(project_root / 'params.yaml', 'r') as f:
        params = yaml.safe_load(f)

    # Note: Using watermass_name vs division dynamically based on target
    if TARGET_REGION in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        REGION_COLUMN = 'watermass_name'
    else:
        REGION_COLUMN = 'division'

    REP_MONTH_SUMMER = params['seasonal_subsets']['representative_months']['Summer']

    logging.info(f"Target Region: {TARGET_REGION} (Column: {REGION_COLUMN})")
    logging.info(f"Representative Summer Month: {REP_MONTH_SUMMER}")

    df = merged_gdf[merged_gdf[REGION_COLUMN] == TARGET_REGION].copy()

    summer_bottom = df[
        (df['surveymont'] == REP_MONTH_SUMMER) &
        (df['saisuipoin'] == 2)
    ].copy()

    summer_bottom['do_'] = pd.to_numeric(summer_bottom['do_'], errors='coerce')
    summer_bottom = summer_bottom.dropna(subset=['do_'])

    if summer_bottom.empty:
        logging.warning(f"No data for {TARGET_REGION}. Exiting.")
        return

    # Pivot data: Rows = zettaicode, Cols = year, Values = do_
    pivot_df = summer_bottom.pivot_table(
        index='zettaicode',
        columns='year',
        values='do_',
        aggfunc='mean'
    )

    pivot_df.index = pivot_df.index.astype(str).str.zfill(8)
    station_mean_do = pivot_df.mean(axis=1).sort_values(ascending=False)
    pivot_df = pivot_df.loc[station_mean_do.index]

    plt.figure(figsize=(20, 30))
    sns.heatmap(
        pivot_df, 
        cmap='RdYlBu', 
        center=4.0,
        cbar_kws={'label': 'Dissolved Oxygen (mg/L)'},
        linewidths=0.01,
        linecolor='gray'
    )
    plt.title(f'Hypoxia Status Over Time per Station - {TARGET_REGION}')
    plt.ylabel('Station (zettaicode) - Sorted by Mean DO (High to Low)')
    plt.xlabel('Year')

    output_path = OUTPUT_DIR / f'hypoxia_status_comparison_{div_clean}_summer.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    logging.info(f"Heatmap saved to {output_path}")

    def calculate_slope(row):
        valid_mask = ~row.isna()
        if valid_mask.sum() < 5:
            return np.nan
        years = row.index[valid_mask].astype(float)
        values = row[valid_mask].values
        slope, _, _, _, _ = stats.linregress(years, values)
        return slope

    slopes = pivot_df.apply(calculate_slope, axis=1).dropna()

    plt.figure(figsize=(10, 6))
    sns.histplot(slopes, bins=20, kde=True, color='purple')
    plt.axvline(0, color='red', linestyle='--')
    plt.title(f'Distribution of DO Trends (Slopes) across Stations - {TARGET_REGION}')
    plt.xlabel('Slope (mg/L per Year)')
    plt.ylabel('Count')
    
    output_path_hist = OUTPUT_DIR / f'do_trends_distribution_{div_clean}_summer.png'
    plt.savefig(output_path_hist, bbox_inches='tight', dpi=300)
    plt.close()
    logging.info(f"Histogram saved to {output_path_hist}")

    slopes_df = slopes.to_frame(name='do_slope_per_year')
    slopes_df.index.name = 'zettaicode'

    output_csv = PROCESSED_DATA_DIR / f'hypoxia_tendency_slopes_{div_clean}_summer.csv'
    slopes_df.to_csv(output_csv)
    logging.info(f"Slopes saved to: {output_csv}")

if __name__ == "__main__":
    main()

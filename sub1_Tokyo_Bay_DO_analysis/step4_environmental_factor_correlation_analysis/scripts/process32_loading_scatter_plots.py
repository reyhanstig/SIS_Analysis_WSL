# -*- coding: utf-8 -*-
import argparse
import sys
from pathlib import Path
import os
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
import seaborn as sns

# --- BOILERPLATE INJECTED BY AGENT ---
CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')
# -------------------------------------

project_root = CURRENT_SCRIPT.parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 150

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    parser.add_argument('--data_type', required=True, choices=['env', 'nutr'])
    parser.add_argument('--param_col', required=True)
    parser.add_argument('--pc_name', required=True, choices=['PC1', 'PC2'])
    args = parser.parse_args()
    
    target_region = args.target_region
    season = args.season
    layer = args.layer
    data_type = args.data_type
    param_col = args.param_col
    pc_name = args.pc_name
    region_slug = target_region.replace(' ', '_')
    
    logging.info(f"Running process32 for {data_type} param {param_col} in {target_region}")
    
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    
    corr_file = subset_dir / f'pca_{data_type}_corr_{pc_name.lower()}.csv'
    if not corr_file.exists():
        logging.error(f"Correlation file not found: {corr_file}")
        return
        
    corr_df = pd.read_csv(corr_file, dtype={'zettaicode': str}).set_index('zettaicode')
    pca_loadings = pd.read_csv(subset_dir / 'pca_loadings.csv', dtype={'zettaicode': str}).set_index('zettaicode')
    
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    if target_region:
        valid_stations = merged_df[merged_df['watermass_name'] == target_region]['zettaicode'].unique()
        corr_df = corr_df[corr_df.index.isin(valid_stations)]
        pca_loadings = pca_loadings[pca_loadings.index.isin(valid_stations)]
        
    divisions = merged_df[['zettaicode', 'division']].drop_duplicates('zettaicode').set_index('zettaicode')
    
    if param_col not in corr_df.columns:
        logging.error(f"Parameter column {param_col} not found in {corr_file}")
        return

    plot_df = pd.DataFrame(index=corr_df.index)
    plot_df['Param_Corr'] = corr_df[param_col]
    
    y_col = f'{pc_name}_Loading'
    plot_df = plot_df.join(pca_loadings[[y_col]])
    plot_df = plot_df.join(divisions['division'])
    plot_df = plot_df.dropna(subset=['Param_Corr', y_col, 'division'])

    if plot_df.empty:
        logging.warning("No data to plot after dropping NaNs.")
        return

    fig, ax = plt.subplots(figsize=(14, 8))

    unique_divisions = plot_df['division'].unique()
    palette = sns.color_palette("tab10", n_colors=len(unique_divisions))

    sns.scatterplot(
        data=plot_df, x='Param_Corr', y=y_col, hue='division', 
        palette=palette, edgecolor='k', s=100, alpha=0.85, ax=ax
    )
    
    ax.axhline(0, color='gray', linestyle='--', zorder=1)
    ax.axvline(0, color='gray', linestyle='--', zorder=1)
    
    for idx, row in plot_df.iterrows():
        ax.annotate(idx, (row['Param_Corr'], row[y_col]),
                    xytext=(4, 4), textcoords='offset points',
                    fontsize=8, alpha=0.8,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.5, ec="none"))
                    
    param_title = param_col.replace('_', ' ')
    for old, new in [('NH4N2', 'NH4-N'), ('NH4N', 'NH4-N'), ('NO3N2', 'NO3-N'), ('NO3N', 'NO3-N'), ('NO2N2', 'NO2-N'), ('NO2N', 'NO2-N'), ('PO4P2', 'PO4-P'), ('PO4P', 'PO4-P')]:
        param_title = param_title.replace(old, new)
    ax.set_title(f"DO ({y_col}) vs. {param_title} Correlation ({target_region})", fontsize=15, fontweight='bold')
    ax.set_xlabel(f"{param_title} (Pearson r with {pc_name})", fontsize=13)
    ax.set_ylabel(f"DO ({y_col})", fontsize=13)
    ax.legend(title='Division', bbox_to_anchor=(1.01, 1), loc='upper left')

    plt.tight_layout()
    safe_param = param_col.replace(' ', '_').replace('/', '_')
    for old, new in [('NH4N2', 'NH4-N'), ('NH4N', 'NH4-N'), ('NO3N2', 'NO3-N'), ('NO3N', 'NO3-N'), ('NO2N2', 'NO2-N'), ('NO2N', 'NO2-N'), ('PO4P2', 'PO4-P'), ('PO4P', 'PO4-P')]:
        safe_param = safe_param.replace(old, new)
    plt.savefig(OUTPUT_DIR / f'do_loading_scatter_{data_type}_{pc_name}_{safe_param}_{region_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

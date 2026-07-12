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
    parser.add_argument('--chunk_idx', type=int, required=True)
    args = parser.parse_args()
    
    target_region = args.target_region
    season = args.season
    layer = args.layer
    data_type = args.data_type
    chunk_idx = args.chunk_idx
    region_slug = target_region.replace(' ', '_')
    
    logging.info(f"Running process33 for {data_type} chunk {chunk_idx} in {target_region}")
    
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    
    corr_df_pc1 = pd.read_csv(subset_dir / f'pca_{data_type}_corr_pc1.csv', dtype={'zettaicode': str}).set_index('zettaicode')
    corr_df_pc2 = pd.read_csv(subset_dir / f'pca_{data_type}_corr_pc2.csv', dtype={'zettaicode': str}).set_index('zettaicode')
    
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    if target_region:
        valid_stations = merged_df[merged_df['watermass_name'] == target_region]['zettaicode'].unique()
        corr_df_pc1 = corr_df_pc1[corr_df_pc1.index.isin(valid_stations)]
        corr_df_pc2 = corr_df_pc2[corr_df_pc2.index.isin(valid_stations)]
        
    if corr_df_pc1.empty or corr_df_pc2.empty:
        logging.warning("No valid stations found.")
        sys.exit(0)

    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    all_station_idx = corr_df_pc1.index.union(corr_df_pc2.index)
    station_lon = stations.loc[stations.index.intersection(all_station_idx), 'longitude']
    sorted_stations = station_lon.sort_values(ascending=True).index.tolist()

    r_cols = [c for c in corr_df_pc1.columns if not c.endswith('_pval') and not c.endswith('_n')]

    CHUNK_SIZE = 30
    chunks = [sorted_stations[i:i + CHUNK_SIZE] for i in range(0, len(sorted_stations), CHUNK_SIZE)]

    if chunk_idx < 0 or chunk_idx >= len(chunks):
        logging.info(f"Chunk index {chunk_idx} is out of bounds. Found {len(chunks)} chunks.")
        # Exit with a special code so main.py knows when to stop looping
        sys.exit(42)

    chunk = chunks[chunk_idx]
    param_names = [n.replace('_', '\n') for n in r_cols]

    fig, axes = plt.subplots(2, 1, figsize=(20, 14))

    for ax, corr_df, pc_name in zip(axes, [corr_df_pc1, corr_df_pc2], ['PC1', 'PC2']):
        present = [s for s in chunk if s in corr_df.index]
        if not present:
            continue
            
        plot_data = corr_df.loc[present, r_cols].T

        sns.heatmap(
            plot_data,
            ax=ax,
            cmap='RdBu_r',
            center=0,
            vmin=-1, vmax=1,
            linewidths=0.3,
            annot=True,
            fmt=".2f",
            annot_kws={"size": 7.5},
            cbar_kws={'label': 'Pearson r', 'shrink': 0.8},
            yticklabels=param_names,
        )

        xtick_labels = []
        for stn in present:
            lon_val = station_lon.get(stn, float('nan'))
            xtick_labels.append(f"{stn}\n({lon_val:.2f}°E)")
            
        ax.set_xticklabels(xtick_labels, fontsize=8, rotation=45, ha='right')
        ax.set_yticklabels(ax.get_yticklabels(), fontsize=10, rotation=0)

        start_rank = chunk_idx * CHUNK_SIZE + 1
        end_rank   = start_rank + len(present) - 1
        ax.set_title(
            f'{pc_name} vs. Parameters ({target_region}) — Stations {start_rank}–{end_rank} (West→East)',
            fontsize=14, fontweight='bold'
        )
        ax.set_xlabel('Station (zettaicode, longitude)', fontsize=12)

    plt.suptitle(
        f'{data_type.upper()} PC–Parameter Correlations Heatmap | Panel {chunk_idx + 1} of {len(chunks)} ',
        fontsize=16, fontweight='bold', y=1.02
    )
    plt.tight_layout()

    output_name = f'correlation_heatmap_{data_type}_{region_slug}_{season}_{layer}_panel{chunk_idx + 1}.png'
    plt.savefig(OUTPUT_DIR / output_name, bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

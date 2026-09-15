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

project_root = CURRENT_SCRIPT.parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths

# Configure plots
plt.style.use(str(project_root / 'project_style.mplstyle'))
plt.rcParams['figure.dpi'] = 150

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    parser.add_argument('--data_type', required=True, choices=['env', 'nutr'])
    args = parser.parse_args()
    
    target_region = args.target_region
    season = args.season
    layer = args.layer
    data_type = args.data_type
    region_slug = target_region.replace(' ', '_')
    
    logging.info(f"Running process31 for {data_type} in {target_region}")
    
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    
    pc1_path = subset_dir / f'pca_{data_type}_corr_pc1.csv'
    pc2_path = subset_dir / f'pca_{data_type}_corr_pc2.csv'
    
    if not pc1_path.exists() or not pc2_path.exists():
        logging.warning(f"Correlation files not found for {target_region} {season} {layer}. Skipping.")
        return
        
    corr_df_pc1 = pd.read_csv(pc1_path, dtype={'zettaicode': str}).set_index('zettaicode')
    corr_df_pc2 = pd.read_csv(pc2_path, dtype={'zettaicode': str}).set_index('zettaicode')
    
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    if target_region:
        valid_stations = merged_df[merged_df['watermass_name'] == target_region]['zettaicode'].unique()
        corr_df_pc1 = corr_df_pc1[corr_df_pc1.index.isin(valid_stations)]
        corr_df_pc2 = corr_df_pc2[corr_df_pc2.index.isin(valid_stations)]
        
    if corr_df_pc1.empty or corr_df_pc2.empty:
        logging.warning(f"No valid stations found for {target_region}")
        return

    # 1. Distribution Boxplot
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(f"Environmental Factor PCA Correlation Distribution - {target_region} (Season: {season} | Layer: {layer} | Data: {data_type})", fontsize=20)

    for ax, corr_df, pc_name in zip(axes, [corr_df_pc1, corr_df_pc2], ['PC1', 'PC2']):
        r_cols = [c for c in corr_df.columns if not c.endswith('_pval') and not c.endswith('_n')]
        melted = corr_df[r_cols].melt(var_name='Parameter', value_name='Pearson_r')
        melted['Parameter'] = melted['Parameter'].str.replace('_', ' ')
        
        sns.boxplot(data=melted, x='Parameter', y='Pearson_r', ax=ax, hue='Parameter', legend=False, palette='Set2')
        ax.axhline(0, color='gray', linestyle='--')
        ax.set_title(f'Distribution of {pc_name} Correlations by Station')
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
        ax.set_ylabel('Pearson r')
        ax.set_ylim(-1.1, 1.1)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f'correlation_distribution_{data_type}_{region_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

    # 2. Significant Diverging Bar Chart
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    fig.suptitle(f"Significant PCA Correlations Count - {target_region} (Season: {season} | Layer: {layer} | Data: {data_type})", fontsize=20)

    for ax, corr_df, pc_name in zip(axes, [corr_df_pc1, corr_df_pc2], ['PC1', 'PC2']):
        r_cols = [c for c in corr_df.columns if not c.endswith('_pval') and not c.endswith('_n')]
        
        counts = []
        for c in r_cols:
            pval_col = f"{c}_pval"
            if pval_col in corr_df.columns:
                sig_pos = ((corr_df[c] > 0) & (corr_df[pval_col] < 0.05)).sum()
                sig_neg = ((corr_df[c] < 0) & (corr_df[pval_col] < 0.05)).sum()
                
                counts.append({
                    'Parameter': c.replace('_', ' '),
                    'Positive': sig_pos,
                    'Negative': -sig_neg, 
                    'Total_Significant': sig_pos + sig_neg
                })
                
        count_df = pd.DataFrame(counts)
        if not count_df.empty:
            count_df = count_df.sort_values(by='Total_Significant', ascending=True)
            
            ax.barh(count_df['Parameter'], count_df['Positive'], color='indianred', label='Significant Positive (r > 0)')
            ax.barh(count_df['Parameter'], count_df['Negative'], color='steelblue', label='Significant Negative (r < 0)')
            ax.axvline(0, color='black', linewidth=1)
            
            ax.set_title(f'Count of Significant Correlations by Station ({pc_name})')
            ax.set_xlabel('Number of Stations')
            ax.set_ylabel('Parameter')
            ax.legend(loc='lower right')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f'correlation_significance_counts_{data_type}_{region_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

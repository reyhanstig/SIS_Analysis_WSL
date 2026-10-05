# -*- coding: utf-8 -*-
import argparse
import sys
from pathlib import Path
import os
import pandas as pd
import numpy as np
import logging
import math
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import pearsonr

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
if str(project_root / 'scripts') not in sys.path:
    sys.path.append(str(project_root / 'scripts'))

from utils.paths import ProjectPaths
from utils.data_loader import load_and_process_data

# Global plot settings
plt.rcParams.update({
    'font.size': 16,
    'axes.labelsize': 18,
    'axes.titlesize': 20,
    'xtick.labelsize': 16,
    'ytick.labelsize': 16,
    'legend.fontsize': 16
})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    args = parser.parse_args()
    
    target_region = args.target_region
    season = args.season
    layer = args.layer
    region_slug = target_region.replace(' ', '_')
    
    logging.info(f"Running process12 for {target_region}")
    
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    
    # Load selected stations
    group_csv = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / "process11_trend_grouping_and_maps" / f'stations_trend_groups_{region_slug}_{season}_{layer}.csv'
    if not group_csv.exists():
        logging.warning(f"Group CSV not found: {group_csv}. Skipping.")
        return
        
    selected_stations = pd.read_csv(group_csv, dtype={'Station_ID': str})
    selected_stations['Station_ID'] = selected_stations['Station_ID'].str.zfill(8)

    # Load correlation data
    env_corr_path = subset_dir / 'pca_env_corr_pc1.csv'
    nutr_corr_path = subset_dir / 'pca_nutr_corr_pc1.csv'
    if not env_corr_path.exists() or not nutr_corr_path.exists():
        logging.warning(f"Correlation data missing for {target_region} {season} {layer}. Skipping.")
        return
        
    corr_pc1_env = pd.read_csv(env_corr_path, dtype={'zettaicode': str})
    corr_pc1_nutr = pd.read_csv(nutr_corr_path, dtype={'zettaicode': str})

    params_env = [c for c in corr_pc1_env.columns if c != 'zettaicode' and not c.endswith('_pval') and not c.endswith('_n') and c != 'Winter_Air_Temp']
    params_nutr = [c for c in corr_pc1_nutr.columns if c != 'zettaicode' and not c.endswith('_pval') and not c.endswith('_n')]

    pca_corr = corr_pc1_env[['zettaicode'] + params_env].rename(columns={c: f"{c}_Corr_PC1" for c in params_env})
    pca_corr = pca_corr.merge(corr_pc1_nutr[['zettaicode'] + params_nutr].rename(columns={c: f"{c}_Corr_PC1" for c in params_nutr}), on='zettaicode', how='outer')

    analysis_df = selected_stations.merge(pca_corr, left_on='Station_ID', right_on='zettaicode', how='inner')

    if 'Summer_Chla_Corr_PC1' not in analysis_df.columns:
        logging.info("Calculating Summer Chl-a correlations...")
        pca_scores = pd.read_csv(subset_dir / 'pca_scores.csv', index_col=0)
        pca_scores.index = pca_scores.index.astype(int)
        
        merged_gdf = load_and_process_data(force_reload=False)
        merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)
        
        layer_map = {'surface': 1, 'bottom': 2}
        layer_idx = layer_map.get(layer.lower(), 2)
        
        mask = (merged_gdf['season'] == season) & (merged_gdf['saisuipoin'] == layer_idx)
        chla_mat = merged_gdf[mask].groupby(['year', 'zettaicode'])['chlorophyl'].mean().unstack()
        
        chla_corrs = {}
        for stn in analysis_df['Station_ID'].unique():
            if stn in chla_mat.columns:
                s_pc = pca_scores['PC1']
                s_env = chla_mat[stn]
                common = s_pc.index.intersection(s_env.index)
                valid = s_pc.loc[common].notna() & s_env.loc[common].notna()
                if valid.sum() >= 5:
                    r, _ = pearsonr(s_pc.loc[common][valid], s_env.loc[common][valid])
                    chla_corrs[stn] = r
        
        analysis_df['Summer_Chla_Corr_PC1'] = analysis_df['Station_ID'].map(chla_corrs)

    params_to_test = [f"{p}_Corr_PC1" for p in params_env + params_nutr]
    if 'Summer_Chla_Corr_PC1' not in params_to_test:
        params_to_test.append('Summer_Chla_Corr_PC1')

    # Prepare data for grouped plotting (Melt)
    params_to_plot = [p for p in params_to_test if p in analysis_df.columns]
    melted_df = analysis_df.melt(id_vars=['Station_ID', 'Group'], value_vars=params_to_plot, 
                                 var_name='Parameter', value_name='Correlation')
    melted_df = melted_df.dropna(subset=['Correlation'])
    if melted_df.empty:
        logging.warning(f"No valid PCA correlations found for {target_region}. Skipping plot.")
        return
        
    melted_df['Parameter'] = melted_df['Parameter'].str.replace('_Corr_PC1', '').str.replace('_', ' ')

    p_values = {}
    for raw_param in params_to_plot:
        display_name = raw_param.replace('_Corr_PC1', '').replace('_', ' ')
        g1 = analysis_df[analysis_df['Group'] == 'Group 1 (Local & Worsening)'][raw_param].dropna()
        g2 = analysis_df[analysis_df['Group'] == 'Group 2 (Regional & Improving)'][raw_param].dropna()
        
        if len(g1) > 0 and len(g2) > 0:
            _, p = stats.mannwhitneyu(g1, g2, alternative='two-sided')
            p_values[display_name] = p
        else:
            p_values[display_name] = 1.0

    # Save P-values for process14
    p_values_df = pd.DataFrame(list(p_values.items()), columns=['Parameter', 'P_Value'])
    p_values_df.to_csv(PROCESSED_DATA_DIR / f'p_values_pca_{region_slug}_{season}_{layer}.csv', index=False)

    # Sort parameters
    param_order = melted_df.groupby('Parameter')['Correlation'].median().sort_values(ascending=False).index

    plt.figure(figsize=(22, 10))
    ax = sns.boxplot(data=melted_df, x='Parameter', y='Correlation', hue='Group', 
                    order=param_order, palette=['indianred', 'steelblue'], showfliers=False)

    sns.stripplot(data=melted_df, x='Parameter', y='Correlation', hue='Group', 
                  order=param_order, dodge=True, palette=['black', 'black'], alpha=0.3, size=4, legend=False)

    for i, param in enumerate(param_order):
        p = p_values.get(param, 1.0)
        if p < 0.001: sig_text = '***'
        elif p < 0.01: sig_text = '**'
        elif p < 0.05: sig_text = '*'
        else: sig_text = 'ns'
        
        y_max = melted_df[melted_df['Parameter'] == param]['Correlation'].max()
        ax.text(i, y_max + 0.08, sig_text, ha='center', va='bottom', color='black', 
                fontweight='bold' if sig_text != 'ns' else 'normal')

    plt.axhline(0, color='black', linestyle='--', alpha=0.5)
    plt.title(f"Significance of Environmental Drivers Between Trend Groups\n{target_region}", pad=25)
    plt.ylabel("Pearson Correlation (r) with PCA PC1")
    plt.xlabel("Environmental Factors")
    labels = [item.get_text() for item in ax.get_xticklabels()]
    new_labels = [l.replace('NH4N', 'NH4-N').replace('NO3N', 'NO3-N').replace('NO2N', 'NO2-N').replace('PO4P', 'PO4-P') for l in labels]
    ax.set_xticks(ax.get_xticks())
    ax.set_xticklabels(new_labels, rotation=45, ha='right')

    handles, labels = ax.get_legend_handles_labels()
    plt.legend(handles[0:2], labels[0:2], title="Group", loc='upper right', frameon=True, shadow=True)
    plt.ylim(melted_df['Correlation'].min() - 0.1, melted_df['Correlation'].max() + 0.2)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f'driver_sensitivity_pca_grouped_{region_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

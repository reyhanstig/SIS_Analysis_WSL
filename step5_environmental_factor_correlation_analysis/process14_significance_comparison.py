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

# Global plot settings
plt.rcParams.update({
    'font.size': 16,
    'axes.labelsize': 18,
    'axes.titlesize': 20,
    'xtick.labelsize': 16,
    'ytick.labelsize': 16,
    'legend.fontsize': 16
})

def get_best_match(raw_name, pca_params, season, layer):
    layer_num = '1' if layer.lower() == 'surface' else '2'
    
    mapping_hints = {
        'Temp': f'{season} {layer_num} WTEMP',
        'Salinity': f'{season} {layer_num} SALT2',
        'Density': f'{season} {layer_num} DENSITY',
        'Stratification': f'{season} Stratification',
        'Chla': f'{season} Chla',
        'COD': f'{season} {layer_num} COD',
        'DOC': f'{season} {layer_num} DOC',
        'TN': f'{season} {layer_num} TN',
        'TP': f'{season} {layer_num} TP',
        'DIN': f'{season} {layer_num} DIN',
        'DIP': f'{season} {layer_num} DIP',
        'PO4P': f'{season} {layer_num} PO4P',
        'NH4N': f'{season} {layer_num} NH4N',
        'NO2N': f'{season} {layer_num} NO2N',
        'NO3N': f'{season} {layer_num} NO3N'
    }
    
    hint = mapping_hints.get(raw_name, raw_name)
    
    # Check exact
    if hint in pca_params:
        return hint
        
    # Check partial
    for p in pca_params:
        # Simplistic matching for Chla
        if 'Chla' in hint and 'Chla' in p:
            return p
        if raw_name.upper() in p.upper() and layer_num in p:
            return p
            
    return hint

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
    
    logging.info(f"Running process14 for {target_region}")
    
    pca_file = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / "process12_pca_sensitivity" / f'p_values_pca_{region_slug}_{season}_{layer}.csv'
    raw_file = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / "process13_raw_sensitivity" / f'p_values_raw_{region_slug}_{season}_{layer}.csv'
    
    if not pca_file.exists() or not raw_file.exists():
        logging.warning("P-value CSVs from process12 and process13 are required. Skipping.")
        return
        
    df_pca = pd.read_csv(pca_file)
    df_raw = pd.read_csv(raw_file)
    
    p_values_pca = dict(zip(df_pca['Parameter'], df_pca['P_Value']))
    p_values_raw = dict(zip(df_raw['Parameter'], df_raw['P_Value']))
    
    raw_params = list(p_values_raw.keys())
    pca_params = list(p_values_pca.keys())
    
    comp_data = []
    for raw_name in raw_params:
        pca_name = get_best_match(raw_name, pca_params, season, layer)
        
        p_raw = p_values_raw.get(raw_name, 1.0)
        p_pca = p_values_pca.get(pca_name, 1.0)
        
        comp_data.append({
            'Parameter': raw_name,
            'Short-Term Variability\n(Raw DO)': p_raw,
            'Long-Term Trend\n(PCA PC1)': p_pca
        })

    comp_df = pd.DataFrame(comp_data).set_index('Parameter')
    comp_df.index = comp_df.index.str.replace('NH4N', 'NH4-N').str.replace('NO3N', 'NO3-N').str.replace('NO2N', 'NO2-N').str.replace('PO4P', 'PO4-P')
    log_df = -np.log10(comp_df + 1e-10)

    annot_df = comp_df.copy()
    for col in annot_df.columns:
        annot_df[col] = annot_df[col].apply(
            lambda p: '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else 'ns'))
        )

    log_df = log_df.sort_values(by=['Long-Term Trend\n(PCA PC1)', 'Short-Term Variability\n(Raw DO)'], ascending=[False, False])
    annot_df = annot_df.reindex(log_df.index)

    plt.figure(figsize=(10, 12))

    cmap = sns.color_palette("Reds", as_cmap=True)
    cmap.set_under("#f0f0f0") 

    ax = sns.heatmap(log_df, annot=annot_df, fmt="", cmap=cmap, 
                     vmin=-np.log10(0.05), vmax=-np.log10(0.001), 
                     linewidths=2, linecolor='white', square=False,
                     cbar_kws={'label': 'Significance Magnitude (-log10 p-value)'},
                     annot_kws={'size': 16, 'weight': 'bold'})

    plt.title(f"Driver Significance: Long-Term vs. Short-Term\n{target_region}", pad=20, weight='bold')
    plt.ylabel(f"Environmental Parameter ({season} {layer.capitalize()})", weight='bold')
    plt.xlabel("Timescale of DO Correlation", weight='bold')

    plt.xticks(fontsize=18)
    plt.yticks(fontsize=18, rotation=0)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f'driver_significance_heatmap_{region_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

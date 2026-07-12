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
from scipy import stats
import yaml

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

with open(ProjectPaths.PROJECT_ROOT / 'params.yaml', 'r') as f:
    project_params = yaml.safe_load(f)

def calc_raw_corr(station_id, param_col, merged_data, season, layer):
    rep_months = project_params['seasonal_subsets']['representative_months'].get(season, [7, 8, 9])
    
    st_data = merged_data[
        (merged_data['zettaicode'] == station_id) & 
        (merged_data['surveymont'].isin(rep_months) if isinstance(rep_months, list) else merged_data['surveymont'] == rep_months)
    ]
    
    layer_map = {'surface': 1, 'bottom': 2}
    layer_idx = layer_map.get(layer.lower(), 2)
    st_data_layer = st_data[st_data['saisuipoin'] == layer_idx].sort_values('year')
    
    do_vals = pd.to_numeric(st_data_layer['do_'], errors='coerce')
    
    if param_col == 'din':
        cols = ['nh4n', 'no2n', 'no3n']
        available_cols = [c for c in cols if c in st_data_layer.columns]
        if available_cols:
            param_vals = st_data_layer[available_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1, min_count=1)
        else:
            param_vals = pd.Series(np.nan, index=st_data_layer.index)
    elif param_col == 'dip':
        col = 'po4p'
        if col in st_data_layer.columns:
            param_vals = pd.to_numeric(st_data_layer[col], errors='coerce')
        else:
            param_vals = pd.Series(np.nan, index=st_data_layer.index)
    elif param_col in st_data_layer.columns:
        param_vals = pd.to_numeric(st_data_layer[param_col], errors='coerce')
    else:
        param_vals = pd.Series(np.nan, index=st_data_layer.index)
    
    valid = ~(do_vals.isna() | param_vals.isna())
    if valid.sum() > 5:
        r, p = stats.pearsonr(do_vals[valid], param_vals[valid])
        return r
    return np.nan

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
    
    logging.info(f"Running process13 for {target_region}")
    
    # Load grouped stations
    group_csv = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / "process11_trend_grouping_and_maps" / f'stations_trend_groups_{region_slug}_{season}_{layer}.csv'
    if not group_csv.exists():
        logging.error(f"Group CSV not found: {group_csv}")
        sys.exit(1)
        
    analysis_df = pd.read_csv(group_csv, dtype={'Station_ID': str})
    analysis_df['Station_ID'] = analysis_df['Station_ID'].str.zfill(8)
    
    merged_gdf = load_and_process_data(force_reload=False)
    merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

    raw_params = {
        'Temp': 'wtemp', 'Salinity': 'salt', 'COD': 'cod', 'DOC': 'doc', 
        'TN': 'tn', 'TP': 'tp', 'DIN': 'din', 'DIP': 'dip', 
        'NH4N': 'nh4n', 'NO2N': 'no2n', 'NO3N': 'no3n', 
        'PO4P': 'po4p', 'Chla': 'chlorophyl'
    }

    raw_results = []
    for idx, row in analysis_df.iterrows():
        sid = row['Station_ID']
        res = {'Station_ID': sid, 'Group': row['Group']}
        for name, col in raw_params.items():
            res[name] = calc_raw_corr(sid, col, merged_gdf, season, layer)
        raw_results.append(res)

    raw_df = pd.DataFrame(raw_results)

    params_to_plot_raw = list(raw_params.keys())
    melted_raw_df = raw_df.melt(id_vars=['Station_ID', 'Group'], value_vars=params_to_plot_raw, 
                                 var_name='Parameter', value_name='Correlation')

    p_values_raw = {}
    for param in params_to_plot_raw:
        g1 = raw_df[raw_df['Group'] == 'Group 1 (Local & Worsening)'][param].dropna()
        g2 = raw_df[raw_df['Group'] == 'Group 2 (Regional & Improving)'][param].dropna()
        
        if len(g1) > 0 and len(g2) > 0:
            _, p = stats.mannwhitneyu(g1, g2, alternative='two-sided')
            p_values_raw[param] = p
        else:
            p_values_raw[param] = 1.0

    # Save P-values for process14
    p_values_df = pd.DataFrame(list(p_values_raw.items()), columns=['Parameter', 'P_Value'])
    p_values_df.to_csv(PROCESSED_DATA_DIR / f'p_values_raw_{region_slug}_{season}_{layer}.csv', index=False)

    param_order_raw = melted_raw_df.groupby('Parameter')['Correlation'].median().sort_values(ascending=False).index

    plt.figure(figsize=(22, 10))
    ax = sns.boxplot(data=melted_raw_df, x='Parameter', y='Correlation', hue='Group', 
                    order=param_order_raw, palette=['indianred', 'steelblue'], showfliers=False)

    sns.stripplot(data=melted_raw_df, x='Parameter', y='Correlation', hue='Group', 
                  order=param_order_raw, dodge=True, color='black', alpha=0.3, size=4, jitter=True)

    for i, param in enumerate(param_order_raw):
        p = p_values_raw.get(param, 1.0)
        
        if p < 0.001: sig_text = '***'
        elif p < 0.01: sig_text = '**'
        elif p < 0.05: sig_text = '*'
        else: sig_text = 'ns'
        
        y_max = melted_raw_df[melted_raw_df['Parameter'] == param]['Correlation'].max()
        ax.text(i, y_max + 0.08, sig_text, ha='center', va='bottom', color='black', 
                fontweight='bold' if sig_text != 'ns' else 'normal')

    plt.axhline(0, color='black', linestyle='--', alpha=0.5)
    plt.title(f"Significance of Raw Environmental Drivers Between Trend Groups\n{target_region}", pad=25)
    plt.ylabel(f"Pearson Correlation (r) with Raw {season} {layer.capitalize()} DO")
    plt.xlabel("Environmental Factors")
    plt.xticks(rotation=45, ha='right')

    handles, labels = ax.get_legend_handles_labels()
    plt.legend(handles[0:2], labels[0:2], title="Group", loc='upper right', frameon=True, shadow=True)
    plt.ylim(melted_raw_df['Correlation'].min() - 0.1, melted_raw_df['Correlation'].max() + 0.2)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f'driver_sensitivity_raw_grouped_{region_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

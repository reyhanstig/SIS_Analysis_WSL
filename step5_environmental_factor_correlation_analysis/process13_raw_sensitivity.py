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

from process01_data_integrity_and_correlation import MatrixBuilder, build_permutation_matrices

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

LAYER_CODES = [1, 2]  # saisuipoin: 1 = surface, 2 = bottom
DEFAULT_SEASONS = ['Spring', 'Summer', 'Autumn', 'Winter']
MIN_YEARS = 6  # same threshold as before (> 5 valid pairs)


def load_correlation_seasons():
    """Return the parameter seasons to permute over from step5_parameter.csv."""
    param_file = CURRENT_SCRIPT.parent / 'step5_parameter.csv'
    if not param_file.exists():
        logging.warning(f"{param_file} not found. Using default seasons {DEFAULT_SEASONS}.")
        return DEFAULT_SEASONS
    df_p = pd.read_csv(param_file)
    params = dict(zip(df_p['parameter_name'], df_p['value']))
    value = params.get('correlation_seasons', ', '.join(DEFAULT_SEASONS))
    return [s.strip() for s in str(value).split(',')]


def calc_raw_corr(do_series, param_series):
    """Pearson r between two yearly series of one station (requires > 5 common years)."""
    pair = pd.concat([do_series, param_series], axis=1, join='inner').dropna()
    if len(pair) >= MIN_YEARS and pair.iloc[:, 0].std() > 0 and pair.iloc[:, 1].std() > 0:
        r, _ = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
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
        logging.warning(f"Group CSV not found: {group_csv}. Skipping.")
        return
        
    analysis_df = pd.read_csv(group_csv, dtype={'Station_ID': str})
    analysis_df['Station_ID'] = analysis_df['Station_ID'].str.zfill(8)
    
    merged_gdf = load_and_process_data(force_reload=False)
    merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)
    # Only the grouped stations are needed
    merged_gdf = merged_gdf[merged_gdf['zettaicode'].isin(analysis_df['Station_ID'])]
    
    stations = merged_gdf[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    builder = MatrixBuilder(merged_gdf, stations)

    # DO of the analysed subset (season / layer of the trend groups)
    layer_map = {'surface': 1, 'bottom': 2}
    do_layer_code = layer_map.get(layer.lower(), 2)
    do_matrix = builder.raw('do_', season, do_layer_code)

    corr_params_df = pd.read_csv(CURRENT_SCRIPT.parent / 'step5_correlation_parameters.csv')
    corr_seasons = load_correlation_seasons()
    
    # We need both env and nutr permutations
    matrices_env, names_env = build_permutation_matrices(builder, corr_params_df, 'env', corr_seasons)
    matrices_nutr, names_nutr = build_permutation_matrices(builder, corr_params_df, 'nutr', corr_seasons)
    
    param_matrices = dict(zip(names_env + names_nutr, matrices_env + matrices_nutr))

    raw_results = []
    for idx, row in analysis_df.iterrows():
        sid = row['Station_ID']
        res = {'Station_ID': sid, 'Group': row['Group']}
        do_series = do_matrix[sid] if sid in do_matrix.columns else None
        for perm_name, mat in param_matrices.items():
            if do_series is None or sid not in mat.columns:
                res[perm_name] = np.nan
            else:
                res[perm_name] = calc_raw_corr(do_series, mat[sid])
        raw_results.append(res)

    raw_df = pd.DataFrame(raw_results)

    params_to_plot_raw = list(param_matrices.keys())
    melted_raw_df = raw_df.melt(id_vars=['Station_ID', 'Group'], value_vars=params_to_plot_raw, 
                                 var_name='Parameter', value_name='Correlation')
    melted_raw_df = melted_raw_df.dropna(subset=['Correlation'])

    if melted_raw_df.empty:
        logging.warning(f"No valid raw correlations found for {target_region}. Skipping plot.")
        return

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

    # Width scales with the number of parameter permutations so labels stay legible
    plt.figure(figsize=(max(22, 0.45 * len(param_order_raw)), 10))
    ax = sns.boxplot(data=melted_raw_df, x='Parameter', y='Correlation', hue='Group', 
                    order=param_order_raw, palette=['indianred', 'steelblue'], showfliers=False)

    sns.stripplot(data=melted_raw_df, x='Parameter', y='Correlation', hue='Group', 
                  order=param_order_raw, dodge=True, palette=['black', 'black'], alpha=0.3, size=4, legend=False)

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
    labels = [item.get_text() for item in ax.get_xticklabels()]
    new_labels = [l.replace('NH4N', 'NH4-N').replace('NO3N', 'NO3-N').replace('NO2N', 'NO2-N').replace('PO4P', 'PO4-P') for l in labels]
    ax.set_xticks(ax.get_xticks())
    ax.set_xticklabels(new_labels, rotation=45, ha='right')

    handles, labels = ax.get_legend_handles_labels()
    plt.legend(handles[0:2], labels[0:2], title="Group", loc='upper right', frameon=True, shadow=True)
    plt.ylim(melted_raw_df['Correlation'].min() - 0.1, melted_raw_df['Correlation'].max() + 0.2)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f'driver_sensitivity_raw_grouped_{region_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

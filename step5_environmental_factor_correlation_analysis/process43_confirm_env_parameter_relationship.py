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
from scipy.stats import linregress
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

# Apply global project style
style_path = ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'
if style_path.exists():
    plt.style.use(str(style_path))

with open(ProjectPaths.PROJECT_ROOT / 'params.yaml', 'r') as f:
    project_params = yaml.safe_load(f)

def parse_param(param_str):
    parts = param_str.split('_')
    season = parts[0]
    
    if param_str.endswith('Stratification'):
        return {'season': season, 'layer': 2, 'col': 'stratification', 'title': param_str.replace('_', ' '), 'unit': 'kg/m³'}
    elif param_str.endswith('Wind_Speed'):
        return {'season': season, 'layer': 1, 'col': 'fusoku', 'title': param_str.replace('_', ' '), 'unit': 'm/s'}
    elif param_str.endswith('Air_Temp'):
        return {'season': season, 'layer': 1, 'col': 'temp', 'title': param_str.replace('_', ' '), 'unit': '°C'}
    
    if len(parts) < 3:
        return {'season': season, 'layer': 1, 'col': param_str.lower(), 'title': param_str, 'unit': ''}
        
    layer = int(parts[1])
    raw_col = "_".join(parts[2:]).lower()
    if raw_col.endswith('2'):
        raw_col = raw_col[:-1]
        
    col_map = {
        'wtemp': ('wtemp', '°C'),
        'salt': ('salt', 'PSU'),
        'density': ('density', 'kg/m³'),
        'chla': ('chlorophyl', 'μg/L'),
        'din': ('din', 'mg/L'),
        'dip': ('po4p', 'mg/L'),
        'tn': ('tn', 'mg/L'),
        'tp': ('tp', 'mg/L'),
        'cod': ('cod', 'mg/L'),
        'doc': ('doc', 'mg/L'),
        'nh4n': ('nh4n', 'mg/L'),
        'no2n': ('no2n', 'mg/L'),
        'no3n': ('no3n', 'mg/L'),
        'po4p': ('po4p', 'mg/L')
    }
    
    col, unit = col_map.get(raw_col, (raw_col, ''))
    layer_str = "Surface" if layer == 1 else "Bottom"
    
    display_name = raw_col.upper()
    if display_name == 'NH4N': display_name = 'NH4-N'
    elif display_name == 'NO3N': display_name = 'NO3-N'
    elif display_name == 'NO2N': display_name = 'NO2-N'
    elif display_name == 'PO4P': display_name = 'PO4-P'
    
    title = f"{layer_str} {season} {display_name}"
    
    return {'season': season, 'layer': layer, 'col': col, 'title': title, 'unit': unit}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pc_name', required=True)
    parser.add_argument('--param', required=True)
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    parser.add_argument('--data_type', required=True, choices=['env', 'nutr'])
    args = parser.parse_args()
    
    target_region = args.target_region
    season = args.season
    layer = args.layer
    pc_name = args.pc_name
    param_str = args.param
    data_type = args.data_type
    
    region_slug = target_region.replace(' ', '_')
    
    logging.info(f"Running process43 for {target_region}, param: {param_str}, PC: {pc_name}")
    
    # 1. Parse param
    p_info = parse_param(param_str)
    
    # 2. Read correlation data
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    corr_file = subset_dir / f"pca_{data_type}_corr_{pc_name.lower()}.csv"
    if not corr_file.exists():
        logging.error(f"Correlation file not found: {corr_file}")
        return
        
    df_corr = pd.read_csv(corr_file, index_col=0, dtype={0: str})
    df_corr.index = df_corr.index.str.zfill(8)
    
    if param_str not in df_corr.columns:
        logging.error(f"Param {param_str} not found in {corr_file}")
        return
        
    pval_col = f"{param_str}_pval"
    
    # 3. Filter stations (pval <= 0.05 AND |r| > 0)
    # Using the same logic as process42
    sig_stations = df_corr[(df_corr[pval_col] <= 0.05) & (df_corr[param_str].abs() > 0)].index.tolist()
    if not sig_stations:
        logging.info(f"No significant stations found for {param_str} with {pc_name}")
        return

    # 4. Load PC scores
    pca_scores_file = subset_dir / 'pca_scores.csv'
    if not pca_scores_file.exists():
        logging.error(f"PCA scores file not found: {pca_scores_file}")
        return
    pca_scores = pd.read_csv(pca_scores_file, index_col=0)
    pca_scores.index = pca_scores.index.astype(int)

    # 5. Load raw data
    merged_gdf = load_and_process_data(force_reload=False)
    merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

    # Filter available stations for the target region to map sub-basins
    if target_region in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        region_stations = merged_gdf[merged_gdf['watermass_name'] == target_region]
    else:
        region_stations = merged_gdf[merged_gdf['division'] == target_region]
        
    st_division_map = region_stations[['zettaicode', 'division']].drop_duplicates().set_index('zettaicode')['division'].to_dict()
    
    # Restrict sig_stations to the current target region
    target_stations = [st for st in sig_stations if st in st_division_map]
    if not target_stations:
        logging.info(f"No significant stations inside {target_region}")
        return

    param_season = p_info['season']
    
    # Use the pre-computed 'season' column to safely include all months for the season
    season_data = merged_gdf[
        (merged_gdf['season'] == param_season) & 
        (merged_gdf['zettaicode'].isin(target_stations))
    ].copy()

    if p_info['col'] == 'din' and 'din' not in season_data.columns:
        nh4 = pd.to_numeric(season_data['nh4n'], errors='coerce').fillna(0)
        no2 = pd.to_numeric(season_data['no2n'], errors='coerce').fillna(0)
        no3 = pd.to_numeric(season_data['no3n'], errors='coerce').fillna(0)
        season_data['din'] = nh4 + no2 + no3
        all_nan = season_data['nh4n'].isna() & season_data['no2n'].isna() & season_data['no3n'].isna()
        season_data.loc[all_nan, 'din'] = np.nan

    if p_info['col'] in ['stratification', 'density']:
        import gsw
        season_data['density'] = gsw.rho(pd.to_numeric(season_data['salt'], errors='coerce'), pd.to_numeric(season_data['wtemp'], errors='coerce'), 0) - 1000

    if p_info['col'] == 'stratification':
        surf = season_data[season_data['saisuipoin'] == 1].groupby(['zettaicode', 'surveyyear'])['density'].mean()
        bot = season_data[season_data['saisuipoin'] == 2].groupby(['zettaicode', 'surveyyear'])['density'].mean()
        strat = (bot - surf).reset_index().rename(columns={'density': 'stratification'})
        layer_data = strat
    else:
        layer_data = season_data[season_data['saisuipoin'] == p_info['layer']].copy()
        layer_data[p_info['col']] = pd.to_numeric(layer_data[p_info['col']], errors='coerce')
        # Aggregate by surveyyear to prevent zigzagging per station
        layer_data = layer_data.groupby(['zettaicode', 'surveyyear'])[p_info['col']].mean().reset_index()

    # Determine unique basins to plot
    if target_region == 'Seto Inland Sea':
        basins = sorted(list(set(st_division_map.values())))
    else:
        basins = [target_region]
        for st in target_stations:
            st_division_map[st] = target_region
            
    safe_title = param_str.replace(' ', '_').replace('/', '_')
    for old, new in [('NH4N2', 'NH4-N'), ('NH4N', 'NH4-N'), ('NO3N2', 'NO3-N'), ('NO3N', 'NO3-N'), ('NO2N2', 'NO2-N'), ('NO2N', 'NO2-N'), ('PO4P2', 'PO4-P'), ('PO4P', 'PO4-P')]:
        safe_title = safe_title.replace(old, new)

    for basin in basins:
        basin_slug = basin.replace(' ', '_')
        div_stations = [s for s in target_stations if st_division_map.get(s) == basin]
        
        if not div_stations:
            continue
            
        # Get regional average for the basin
        basin_data = layer_data[layer_data['zettaicode'].isin(div_stations)]
        if basin_data.empty or basin_data[p_info['col']].isna().all():
            continue
            
        regional_avg = basin_data.groupby('surveyyear')[p_info['col']].mean()
        regional_avg.index = regional_avg.index.astype(int)
        
        analysis_df = pd.DataFrame({
            'PC_Score': pca_scores[pc_name],
            'Regional_Param_Avg': regional_avg
        }).dropna()
        
        if len(analysis_df) < 3:
            continue
            
        slope, intercept, r_value, p_value, std_err = linregress(analysis_df['PC_Score'], analysis_df['Regional_Param_Avg'])
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        sns.regplot(
            data=analysis_df, 
            x='PC_Score', 
            y='Regional_Param_Avg',
            ax=ax,
            scatter_kws={'s': 80, 'alpha': 0.7, 'edgecolor': 'k', 'color': 'steelblue'},
            line_kws={'color': 'indianred', 'linewidth': 2.5}
        )
        
        for idx, row in analysis_df.iterrows():
            ax.annotate(str(idx), (row['PC_Score'], row['Regional_Param_Avg']), 
                        xytext=(5, 5), textcoords='offset points', fontsize=10, alpha=0.7)
        
        ax.set_title(f"Regional Relationship: {pc_name} vs {p_info['title']}\n{basin} (Significant Stations)", fontsize=16, fontweight='bold')
        ax.set_xlabel(f"{pc_name} Score", fontsize=14)
        ax.set_ylabel(f"Regional Avg: {p_info['title']} [{p_info['unit']}]", fontsize=14)
        ax.grid(True, linestyle='--', alpha=0.5)
        
        stats_text = f"$R^2 = {r_value**2:.3f}$\n$p = {p_value:.3e}$"
        props = dict(boxstyle='round', facecolor='whitesmoke', alpha=0.8, edgecolor='gray')
        ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=14,
                verticalalignment='top', bbox=props)
        
        basin_out_dir = OUTPUT_DIR / basin_slug
        basin_out_dir.mkdir(parents=True, exist_ok=True)
        
        plt.tight_layout()
        plt.savefig(basin_out_dir / f'scatter_{pc_name}_{safe_title}_{basin_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
        plt.close(fig)

    logging.info(f"Finished processing scatter plots for {target_region}")

if __name__ == '__main__':
    main()

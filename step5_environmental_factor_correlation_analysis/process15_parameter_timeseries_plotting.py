# -*- coding: utf-8 -*-
import argparse
import sys
from pathlib import Path
import os
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import yaml

# --- BOILERPLATE INJECTED BY AGENT ---
CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
# Loop orchestration handles rm_tree for OUTPUT_DIR
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

# Load parameters from CSV
step5_params_df = pd.read_csv(CURRENT_SCRIPT.parent / 'step5_parameter.csv', index_col='parameter_name')
ts_params_file = step5_params_df.loc['ts_params_file', 'value']
ts_params_df = pd.read_csv(CURRENT_SCRIPT.parent / ts_params_file)
ts_params = ts_params_df.to_dict('records')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    parser.add_argument('--param_idx', type=int, required=True)
    args = parser.parse_args()
    
    target_region = args.target_region
    season = args.season
    layer = args.layer
    param_idx = args.param_idx
    region_slug = target_region.replace(' ', '_')
    
    if param_idx < 0 or param_idx >= len(ts_params):
        logging.error(f"Invalid param_idx {param_idx}")
        sys.exit(1)
        
    param = ts_params[param_idx]
    
    logging.info(f"Running process15 for {target_region}, param: {param['title']}")
    
    # Load grouped stations
    group_csv = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / "process11_trend_grouping_and_maps" / f'stations_trend_groups_{region_slug}_{season}_{layer}.csv'
    if not group_csv.exists():
        logging.warning(f"Group CSV not found: {group_csv}. Skipping...")
        sys.exit(0) # Not an error, just skip
        
    selected_stations = pd.read_csv(group_csv, dtype={'Station_ID': str})
    selected_stations['Station_ID'] = selected_stations['Station_ID'].str.zfill(8)

    merged_gdf = load_and_process_data(force_reload=False)
    merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

    st_group_map = selected_stations.set_index('Station_ID')['Group'].to_dict()
    st_division_map = merged_gdf[merged_gdf['zettaicode'].isin(st_group_map.keys())][['zettaicode', 'division']].drop_duplicates().set_index('zettaicode')['division'].to_dict()

    param_season = param.get('season', season)
    
    season_data = merged_gdf[
        (merged_gdf['season'] == param_season) & 
        (merged_gdf['zettaicode'].isin(st_group_map.keys()))
    ].copy()

    if 'din' not in season_data.columns:
        nh4 = pd.to_numeric(season_data['nh4n'], errors='coerce').fillna(0)
        no2 = pd.to_numeric(season_data['no2n'], errors='coerce').fillna(0)
        no3 = pd.to_numeric(season_data['no3n'], errors='coerce').fillna(0)
        season_data['din'] = nh4 + no2 + no3
        all_nan = season_data['nh4n'].isna() & season_data['no2n'].isna() & season_data['no3n'].isna()
        season_data.loc[all_nan, 'din'] = np.nan

    colors = {
        'Group 1 (Local & Worsening)': 'indianred',
        'Group 2 (Regional & Improving)': 'steelblue'
    }

    legend_elements = [
        Line2D([0], [0], color='indianred', marker='o', markersize=10, label='Group 1 (Worsening)', linewidth=2),
        Line2D([0], [0], color='steelblue', marker='o', markersize=10, label='Group 2 (Improving)', linewidth=2)
    ]
    
    if param['col'] == 'stratification':
        import gsw
        # Compute density
        season_data['density'] = gsw.rho(pd.to_numeric(season_data['salt'], errors='coerce'), pd.to_numeric(season_data['wtemp'], errors='coerce'), 0) - 1000
        
        # Calculate stratification = bottom - surface (aggregated by mean)
        surf = season_data[season_data['saisuipoin'] == 1].groupby(['zettaicode', 'surveyyear'])['density'].mean()
        bot = season_data[season_data['saisuipoin'] == 2].groupby(['zettaicode', 'surveyyear'])['density'].mean()
        strat = (bot - surf).reset_index().rename(columns={'density': 'stratification'})
        
        layer_data = strat
    else:
        layer_data = season_data[season_data['saisuipoin'] == param['layer']].copy()
        layer_data[param['col']] = pd.to_numeric(layer_data[param['col']], errors='coerce')
        layer_data = layer_data.groupby(['zettaicode', 'surveyyear'])[param['col']].mean().reset_index()

    # Determine unique basins to plot
    if target_region == 'Seto Inland Sea':
        basins = sorted(list(set(st_division_map.values())))
    else:
        basins = [target_region]
        # For a single basin that isn't sub-divided, map all stations to it so they plot.
        # Actually `st_division_map` might contain NaN or the `target_region` itself.
        for st in st_group_map.keys():
            st_division_map[st] = target_region
            
    safe_title = param['title'].replace(' ', '_').replace('-', '_')

    for basin in basins:
        basin_slug = basin.replace(' ', '_')
        div_stations = [s for s, d in st_division_map.items() if d == basin]
        
        if not div_stations:
            continue
            
        fig, ax = plt.subplots(figsize=(10, 6))
        
        plotted_any = False
        for st in div_stations:
            st_df = layer_data[layer_data['zettaicode'] == st].sort_values('surveyyear')
            if st_df.empty or st_df[param['col']].isna().all():
                continue
                
            group = st_group_map.get(st)
            if not group: continue
            
            ax.plot(st_df['surveyyear'], st_df[param['col']], color=colors[group], 
                    marker='o', markersize=5, alpha=0.7, linewidth=2)
            plotted_any = True
            
        if not plotted_any:
            plt.close(fig)
            continue
            
        ax.set_title(f"{param['title']} Time Series\n{basin}", fontsize=20, fontweight='bold')
        ax.set_ylabel(f"{param['title']} [{param['unit']}]", fontsize=16)
        ax.set_xlabel('Year', fontsize=16)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.tick_params(labelsize=14)
        
        ax.legend(handles=legend_elements, loc='best', fontsize=12, frameon=True)
        
        # Save output in subfolder per basin
        basin_out_dir = OUTPUT_DIR / basin_slug
        basin_out_dir.mkdir(parents=True, exist_ok=True)
        
        plt.tight_layout()
        plt.savefig(basin_out_dir / f'ts_{safe_title}_{basin_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
        plt.close(fig)

    logging.info(f"Finished processing time series for {target_region}")

if __name__ == '__main__':
    main()

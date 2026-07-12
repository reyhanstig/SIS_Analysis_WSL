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

# List of target divisions
target_divisions = [
    'Suo Nada', 'Hiroshima Bay', 'Hiuchi Nada', 'Bingo Nada', 
    'Bisan Seto', 'Harima Nada', 'Osaka Bay', 'Kii Channel', 'Aki Nada'
]

ts_params = [
    {'title': 'Surface Summer DO', 'col': 'do_', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer DO', 'col': 'do_', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Summer SST', 'col': 'wtemp', 'layer': 1, 'unit': '°C'},
    {'title': 'Summer SBT', 'col': 'wtemp', 'layer': 2, 'unit': '°C'},
    {'title': 'Summer SSS', 'col': 'salt', 'layer': 1, 'unit': 'PSU'},
    {'title': 'Summer SBS', 'col': 'salt', 'layer': 2, 'unit': 'PSU'},
    {'title': 'Surface Summer Chl-a', 'col': 'chlorophyl', 'layer': 1, 'unit': 'μg/L'},
    {'title': 'Bottom Summer Chl-a', 'col': 'chlorophyl', 'layer': 2, 'unit': 'μg/L'},
    {'title': 'Surface Summer TN', 'col': 'tn', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer TN', 'col': 'tn', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer TP', 'col': 'tp', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer TP', 'col': 'tp', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer DIN', 'col': 'din', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer DIN', 'col': 'din', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer DIP', 'col': 'po4p', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer DIP', 'col': 'po4p', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer COD', 'col': 'cod', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer COD', 'col': 'cod', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer DOC', 'col': 'doc', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer DOC', 'col': 'doc', 'layer': 2, 'unit': 'mg/L'}
]

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
        logging.error(f"Group CSV not found: {group_csv}")
        sys.exit(1)
        
    selected_stations = pd.read_csv(group_csv, dtype={'Station_ID': str})
    selected_stations['Station_ID'] = selected_stations['Station_ID'].str.zfill(8)

    merged_gdf = load_and_process_data(force_reload=False)
    merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

    st_group_map = selected_stations.set_index('Station_ID')['Group'].to_dict()
    st_division_map = merged_gdf[merged_gdf['zettaicode'].isin(st_group_map.keys())][['zettaicode', 'division']].drop_duplicates().set_index('zettaicode')['division'].to_dict()

    rep_months = project_params['seasonal_subsets']['representative_months'].get(season, [7, 8, 9])
    
    summer_data = merged_gdf[
        (merged_gdf['surveymont'].isin(rep_months) if isinstance(rep_months, list) else merged_gdf['surveymont'] == rep_months) & 
        (merged_gdf['zettaicode'].isin(st_group_map.keys()))
    ].copy()

    if 'din' not in summer_data.columns:
        nh4 = pd.to_numeric(summer_data['nh4n'], errors='coerce').fillna(0)
        no2 = pd.to_numeric(summer_data['no2n'], errors='coerce').fillna(0)
        no3 = pd.to_numeric(summer_data['no3n'], errors='coerce').fillna(0)
        summer_data['din'] = nh4 + no2 + no3
        all_nan = summer_data['nh4n'].isna() & summer_data['no2n'].isna() & summer_data['no3n'].isna()
        summer_data.loc[all_nan, 'din'] = np.nan

    colors = {
        'Group 1 (Local & Worsening)': 'indianred',
        'Group 2 (Regional & Improving)': 'steelblue'
    }

    legend_elements = [
        Line2D([0], [0], color='indianred', marker='o', markersize=10, label='Group 1 (Worsening)', linewidth=2),
        Line2D([0], [0], color='steelblue', marker='o', markersize=10, label='Group 2 (Improving)', linewidth=2)
    ]

    fig, axes = plt.subplots(3, 3, figsize=(24, 15), sharex=True, sharey=True)
    fig.suptitle(f"{param['title']} [{param['unit']}] ({target_region})", fontsize=30, fontweight='bold', y=0.96)
    
    fig.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.98, 0.965), 
               fontsize=22, frameon=False, ncol=1)
    
    axes = axes.flatten()
    
    layer_data = summer_data[summer_data['saisuipoin'] == param['layer']].copy()
    layer_data[param['col']] = pd.to_numeric(layer_data[param['col']], errors='coerce')
    
    for i, div in enumerate(target_divisions):
        if i >= len(axes): break
        ax = axes[i]
        div_stations = [s for s, d in st_division_map.items() if d == div]
        
        for st in div_stations:
            st_df = layer_data[layer_data['zettaicode'] == st].sort_values('year')
            if st_df.empty or st_df[param['col']].isna().all():
                continue
                
            group = st_group_map.get(st)
            if not group: continue
            
            ax.plot(st_df['year'], st_df[param['col']], color=colors[group], 
                    marker='o', markersize=4, alpha=0.6, linewidth=2)
            
        ax.set_title(div, fontsize=24, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.5)
        
        if i >= 6:
            ax.set_xlabel('Year', fontsize=24)
        if i % 3 == 0:
            ax.set_ylabel(param['title'], fontsize=24)
        
        ax.tick_params(labelsize=24)

    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    safe_title = param['title'].replace(' ', '_').replace('-', '_')
    plt.savefig(OUTPUT_DIR / f'ts_{safe_title}_{region_slug}_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

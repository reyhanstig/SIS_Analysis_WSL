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
        # Fallback if parsing fails
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
    
    target_region = args.target_region.strip()
    season = args.season.strip()
    layer = args.layer.strip()
    pc_name = args.pc_name.strip()
    data_type = args.data_type.strip()
    
    region_slug = target_region.replace(' ', '_')
    
    logging.info(f"Running process42 for {target_region}, PC: {pc_name}")
    
    # 2. Read correlation data
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    corr_file = subset_dir / f"pca_{data_type}_corr_{pc_name.lower()}.csv"
    if not corr_file.exists():
        logging.error(f"Correlation file not found: {corr_file}")
        return
        
    df_corr = pd.read_csv(corr_file, index_col=0, dtype={0: str})
    df_corr.index = df_corr.index.str.zfill(8)
    
    if args.param.strip() == 'all':
        params_to_process = [c for c in df_corr.columns if f"{c}_pval" in df_corr.columns]
    else:
        params_to_process = [args.param.strip()]
        
    # Load PC scores
    if target_region in ['Seto Inland Sea']:
        pc_scores_file = subset_dir / 'pca_scores.csv'
    else:
        out_name = target_region.replace(' ', '_').lower()
        pc_scores_file = ProjectPaths.PROCESSED_DATA_DIR / 'step4_PCA_analysis' / 'process11_calculate_pca_explained_variance_per_bay_raw' / out_name / f"pca_scores_{out_name}.csv"

    if not pc_scores_file.exists():
        logging.error(f"PC scores file not found: {pc_scores_file}")
        return
    pc_scores = pd.read_csv(pc_scores_file, index_col=0)

    # 4. Load raw data
    merged_gdf = load_and_process_data(force_reload=False)
    merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

    # Filter available stations for the target region to map sub-basins
    if target_region in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        region_stations = merged_gdf[merged_gdf['watermass_name'] == target_region]
    else:
        region_stations = merged_gdf[merged_gdf['division'] == target_region]
        
    st_division_map = region_stations[['zettaicode', 'division']].drop_duplicates().set_index('zettaicode')['division'].to_dict()
    
    for param_str in params_to_process:
        if param_str not in df_corr.columns:
            logging.error(f"Param {param_str} not found in {corr_file}")
            continue
            
        p_info = parse_param(param_str)
        pval_col = f"{param_str}_pval"
        
        # 3. Filter stations (pval <= 0.05 AND |r| > 0)
        sig_df = df_corr[(df_corr[pval_col] <= 0.05) & (df_corr[param_str].abs() > 0)]
        sig_stations = sig_df.index.tolist()
        if not sig_stations:
            logging.info(f"No significant stations found for {param_str} with {pc_name}")
            continue

        corr_dict = sig_df[param_str].to_dict()

        # Restrict sig_stations to the current target region
        target_stations = [st for st in sig_stations if st in st_division_map]
        if not target_stations:
            logging.info(f"No significant stations inside {target_region} for {param_str}")
            continue

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
            _salt = pd.to_numeric(season_data['salt'], errors='coerce')
            _wtemp = pd.to_numeric(season_data['wtemp'], errors='coerce')
            _SA = gsw.SA_from_SP(_salt, 0, season_data['longitude'], season_data['latitude'])
            _CT = gsw.CT_from_t(_SA, _wtemp, 0)
            season_data['density'] = gsw.sigma0(_SA, _CT)

        if p_info['col'] == 'stratification':
            surf = season_data[season_data['saisuipoin'] == 1].groupby(['zettaicode', 'surveyyear'])['density'].mean()
            bot = season_data[season_data['saisuipoin'] == 2].groupby(['zettaicode', 'surveyyear'])['density'].mean()
            strat = (bot - surf).reset_index().rename(columns={'density': 'stratification'})
            layer_data = strat
        else:
            layer_data = season_data[season_data['saisuipoin'] == p_info['layer']].copy()
            layer_data[p_info['col']] = pd.to_numeric(layer_data[p_info['col']], errors='coerce')
            # Aggregate by surveyyear to prevent zigzagging
            layer_data = layer_data.groupby(['zettaicode', 'surveyyear'])[p_info['col']].mean().reset_index()

        # Determine unique basins to plot
        if target_region == 'Seto Inland Sea':
            basins = sorted(list(set(st_division_map.values())))
        else:
            basins = [target_region]
            for st in target_stations:
                st_division_map[st] = target_region
                
        safe_title = param_str.replace(' ', '_').replace('/', '_').replace('Bottom', 'bottom').replace('Surface', 'surface')
        for old, new in [('NH4N2', 'NH4-N'), ('NH4N', 'NH4-N'), ('NO3N2', 'NO3-N'), ('NO3N', 'NO3-N'), ('NO2N2', 'NO2-N'), ('NO2N', 'NO2-N'), ('PO4P2', 'PO4-P'), ('PO4P', 'PO4-P')]:
            safe_title = safe_title.replace(old, new)

        # Determine dynamic tick years for PC scores
        first_year = pc_scores.index[0]
        last_year = pc_scores.index[-1]
        target_type = type(first_year)
        mid_ticks = [target_type(y) for y in range(1985, 2021, 5) if target_type(y) in pc_scores.index]
        tick_years = sorted(list(set([first_year] + mid_ticks + [last_year])), key=lambda x: int(x))

        for basin in basins:
            basin_slug = basin.replace(' ', '_')
            div_stations = [s for s in target_stations if st_division_map.get(s) == basin]
            
            if not div_stations:
                continue
                
            fig, ax1 = plt.subplots(figsize=(10, 6))
            
            # Plot PC on the primary y-axis
            ax1.plot(pc_scores.index, pc_scores[pc_name], marker='o', label=f'{pc_name} Score', color='tab:blue')
            ax1.axhline(y=0, color='red', linestyle='--', alpha=0.8)
            ax1.set_xlabel('Year', fontsize=16)
            ax1.set_ylabel(f'{pc_name} Score', fontsize=16)
            ax1.set_title(f"{p_info['title']} Time Series\n{basin} (Significantly Correlated with {pc_name})", fontsize=18, fontweight='bold')
            
            ax1.set_xticks(tick_years)
            ax1.tick_params(axis='x', rotation=45, labelsize=14)
            ax1.tick_params(axis='y', labelsize=14)
            ax1.grid(True, linestyle='--', alpha=0.6)
            
            ax2 = ax1.twinx()
            
            all_vals = []
            plotted_any = False
            for st in div_stations:
                st_df = layer_data[layer_data['zettaicode'] == st].sort_values('surveyyear')
                if st_df.empty or st_df[p_info['col']].isna().all():
                    continue
                    
                all_vals.extend(st_df[p_info['col']].dropna().tolist())
                    
                r_val = corr_dict.get(st, 0)
                
                # Use strict red and blue, adjust alpha for saturation based on correlation strength
                base_color = 'red' if r_val > 0 else 'blue'
                abs_r = abs(r_val)
                
                if abs_r >= 0.75: alpha = 0.6
                elif abs_r >= 0.5: alpha = 0.4
                elif abs_r >= 0.25: alpha = 0.25
                else: alpha = 0.1
                
                ax2.plot(st_df['surveyyear'], st_df[p_info['col']], color=base_color, 
                        marker='^', markersize=5, alpha=alpha, linewidth=2, linestyle='--')
                plotted_any = True
                
            if not plotted_any:
                plt.close(fig)
                continue
            
            # --- ALIGNMENT LOGIC ---
            # 1. Make ax1 perfectly symmetric around 0
            y1_min, y1_max = ax1.get_ylim()
            y1_abs_max = max(abs(y1_min), abs(y1_max))
            ax1.set_ylim(-y1_abs_max, y1_abs_max)
            
            # 2. Make ax2 perfectly symmetric around the mean of the plotted environment parameters
            env_mean = np.mean(all_vals)
            ax2.axhline(y=env_mean, color='green', linestyle=':', alpha=0.8, linewidth=2, label='Env Mean')
            
            y2_min, y2_max = ax2.get_ylim()
            y2_abs_max = max(abs(y2_max - env_mean), abs(y2_min - env_mean))
            ax2.set_ylim(env_mean - y2_abs_max, env_mean + y2_abs_max)
            # -----------------------
                
            ax2.set_ylabel(f"{p_info['title']} [{p_info['unit']}]", fontsize=16)
            ax2.tick_params(axis='y', labelsize=14)
            
            # Add legend
            custom_lines = [
                Line2D([0], [0], color='tab:blue', marker='o', lw=2),
                Line2D([0], [0], color='green', linestyle=':', lw=2),
                Line2D([0], [0], color='red', marker='^', lw=2, linestyle='--'),
                Line2D([0], [0], color='blue', marker='^', lw=2, linestyle='--')
            ]
            ax1.legend(custom_lines, [f'{pc_name} Score', f'{p_info["title"]} Mean', f'{p_info["title"]} (+ correlation)', f'{p_info["title"]} (- correlation)'], loc='best', fontsize=12, frameon=True)
            
            # Save output in subfolder per basin and param season
            basin_out_dir = OUTPUT_DIR / basin_slug / param_season
            basin_out_dir.mkdir(parents=True, exist_ok=True)
            
            plt.tight_layout()
            plt.savefig(basin_out_dir / f'ts_{pc_name}_{safe_title}_{basin_slug}.png', bbox_inches='tight', dpi=300)
            plt.close(fig)

    logging.info(f"Finished processing time series for {target_region}")

if __name__ == '__main__':
    main()

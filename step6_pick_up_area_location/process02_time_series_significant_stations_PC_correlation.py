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
    
    layer = int(parts[1])
    raw_col = "_".join(parts[2:]).lower()
    
    df_col = raw_col
    if raw_col == 'chla':
        df_col = 'chlorophyl'
        
    display_col = raw_col
    if display_col.endswith('2'):
        display_col = display_col[:-1]
        
    unit_map = {
        'wtemp': '°C',
        'salt': 'PSU',
        'density': 'kg/m³',
        'chla': 'μg/L',
        'din': 'mg/L',
        'dip': 'mg/L',
        'tn': 'mg/L',
        'tp': 'mg/L',
        'cod': 'mg/L',
        'doc': 'mg/L',
        'nh4n': 'mg/L',
        'no2n': 'mg/L',
        'no3n': 'mg/L',
        'po4p': 'mg/L'
    }
    
    unit = unit_map.get(display_col, '')
    layer_str = "Surface" if layer == 1 else "Bottom"
    
    display_name = display_col.upper()
    if display_name == 'NH4N': display_name = 'NH4-N'
    elif display_name == 'NO3N': display_name = 'NO3-N'
    elif display_name == 'NO2N': display_name = 'NO2-N'
    elif display_name == 'PO4P': display_name = 'PO4-P'
    
    title = f"{layer_str} {season} {display_name}"
    
    return {'season': season, 'layer': layer, 'col': df_col, 'title': title, 'unit': unit}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pc_name', required=True)
    parser.add_argument('--param', required=True)
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--output_prefix', required=False)
    parser.add_argument('--start_year', type=int, required=True)
    parser.add_argument('--end_year', type=int, required=True)
    args = parser.parse_args()
    
    target_region = args.target_region
    pc_name = args.pc_name
    param_str = args.param
    start_year = args.start_year
    end_year = args.end_year
    display_name = args.output_prefix if args.output_prefix else target_region
    prefix_str = display_name.replace(' ', '_').replace('-', '_')
    year_period = f"{start_year}-{end_year}"
    
    logging.info(f"Running process02 for {target_region} ({display_name}), param: {param_str}, PC: {pc_name}, years: {year_period}")
    
    p_info = parse_param(param_str)
    
    process01_dir = Path('/home/reyha/SIS_Analysis_WSL/data/processed/step6_pick_up_area_location/process01_pc_driver_temporal_analysis')
    corr_file = process01_dir / prefix_str / year_period / f"{prefix_str}_{pc_name}_{start_year}_{end_year}_correlations.csv"
    
    if not corr_file.exists():
        logging.error(f"Correlation file not found: {corr_file}")
        return
        
    df_corr = pd.read_csv(corr_file, index_col=0, dtype={0: str})
    df_corr.index = df_corr.index.str.zfill(8)
    
    if param_str not in df_corr.columns:
        logging.error(f"Param {param_str} not found in {corr_file}")
        return
        
    pval_col = f"{param_str}_pval"
    
    sig_df = df_corr[(df_corr[pval_col] <= 0.05) & (df_corr[param_str].abs() > 0)]
    sig_stations = sig_df.index.tolist()
    if not sig_stations:
        logging.info(f"No significant stations found for {param_str} with {pc_name}")
        return

    corr_dict = sig_df[param_str].to_dict()

    merged_gdf = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)
    
    if 'din2' not in merged_gdf.columns:
        merged_gdf['din2'] = merged_gdf['nh4n2'].fillna(0) + merged_gdf['no2n2'].fillna(0) + merged_gdf['no3n2'].fillna(0)
    if 'dip2' not in merged_gdf.columns:
        merged_gdf['dip2'] = merged_gdf['po4p2']

    if 'din' not in merged_gdf.columns:
        merged_gdf['din'] = merged_gdf['nh4n'].fillna(0) + merged_gdf['no2n'].fillna(0) + merged_gdf['no3n'].fillna(0)
    if 'dip' not in merged_gdf.columns:
        merged_gdf['dip'] = merged_gdf['po4p']

    if target_region in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        region_stations = merged_gdf[merged_gdf['watermass_name'] == target_region]
    else:
        region_stations = merged_gdf[merged_gdf['division'] == target_region]
        
    st_division_map = region_stations[['zettaicode']].drop_duplicates().set_index('zettaicode')
    
    target_stations = [st for st in sig_stations if st in st_division_map.index]
    if not target_stations:
        logging.info(f"No significant stations inside {target_region}")
        return

    param_season = p_info['season']
    
    season_data = merged_gdf[
        (merged_gdf['season'] == param_season) & 
        (merged_gdf['zettaicode'].isin(target_stations)) &
        (merged_gdf['surveyyear'] >= start_year) &
        (merged_gdf['surveyyear'] <= end_year)
    ].copy()

    if p_info['col'] in ['stratification', 'density']:
        import gsw
        salt_col = 'salt2' if 'salt2' in season_data.columns else 'salt'
        _salt = pd.to_numeric(season_data[salt_col], errors='coerce')
        _wtemp = pd.to_numeric(season_data['wtemp'], errors='coerce')
        _SA = gsw.SA_from_SP(_salt, 0, season_data['longitude'], season_data['latitude'])
        _CT = gsw.CT_from_t(_SA, _wtemp, 0)
        season_data['density'] = gsw.sigma0(_SA, _CT)

    if p_info['col'] == 'stratification':
        season_data['saisuidept'] = pd.to_numeric(season_data['saisuidept'], errors='coerce')
        surf = season_data[season_data['saisuipoin'] == 1].groupby(['zettaicode', 'surveyyear'])[['density', 'saisuidept']].mean()
        bot = season_data[season_data['saisuipoin'] == 2].groupby(['zettaicode', 'surveyyear'])[['density', 'saisuidept']].mean()
        
        df_merged = bot.join(surf, lsuffix='_bot', rsuffix='_surf')
        df_merged['depth_diff'] = df_merged['saisuidept_bot'] - df_merged['saisuidept_surf']
        df_merged['stratification'] = (df_merged['density_bot'] - df_merged['density_surf']) / df_merged['depth_diff'].replace(0, np.nan)
        
        layer_data = df_merged[['stratification']].reset_index()
    else:
        layer_data = season_data[season_data['saisuipoin'] == p_info['layer']].copy()
        layer_data[p_info['col']] = pd.to_numeric(layer_data[p_info['col']], errors='coerce')
        layer_data = layer_data.groupby(['zettaicode', 'surveyyear'])[p_info['col']].mean().reset_index()

    safe_title = param_str.replace(' ', '_').replace('/', '_')
    for old, new in [('NH4N2', 'NH4-N'), ('NH4N', 'NH4-N'), ('NO3N2', 'NO3-N'), ('NO3N', 'NO3-N'), ('NO2N2', 'NO2-N'), ('NO2N', 'NO2-N'), ('PO4P2', 'PO4-P'), ('PO4P', 'PO4-P')]:
        safe_title = safe_title.replace(old, new)

    legend_elements = [
        Line2D([0], [0], color='red', marker='o', markersize=10, label=f'Positive Correlation with {pc_name}', linewidth=2),
        Line2D([0], [0], color='blue', marker='o', markersize=10, label=f'Negative Correlation with {pc_name}', linewidth=2)
    ]

    fig, ax = plt.subplots(figsize=(10, 6))
    
    plotted_any = False
    for st in target_stations:
        st_df = layer_data[layer_data['zettaicode'] == st].sort_values('surveyyear')
        if st_df.empty or st_df[p_info['col']].isna().all():
            continue
            
        r_val = corr_dict.get(st, 0)
        line_color = 'red' if r_val > 0 else 'blue'
        ax.plot(st_df['surveyyear'], st_df[p_info['col']], color=line_color, 
                marker='o', markersize=5, alpha=0.7, linewidth=2)
        plotted_any = True
        
    if not plotted_any:
        plt.close(fig)
        logging.info("No data plotted.")
        return
        
    ax.set_title(f"{p_info['title']} Time Series\n{display_name} (Significantly Correlated with {pc_name})\n{year_period}", fontsize=18, fontweight='bold')
    ax.set_ylabel(f"{p_info['title']} [{p_info['unit']}]", fontsize=16)
    ax.set_xlabel('Year', fontsize=16)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.tick_params(labelsize=14)
    
    ax.set_xlim(start_year, end_year)
    ax.legend(handles=legend_elements, loc='best', fontsize=12, frameon=True)
    
    out_dir = OUTPUT_DIR / prefix_str / year_period
    out_dir.mkdir(parents=True, exist_ok=True)
    
    plt.tight_layout()
    plt.savefig(out_dir / f'ts_{pc_name}_{safe_title}_{prefix_str}_{year_period}.png', bbox_inches='tight', dpi=300)
    plt.close(fig)

    logging.info(f"Finished processing time series for {display_name} {year_period}")

if __name__ == '__main__':
    main()

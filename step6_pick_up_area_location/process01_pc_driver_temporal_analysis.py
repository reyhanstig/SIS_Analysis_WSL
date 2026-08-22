import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import pandas as pd
import numpy as np
import matplotlib.colors as mcolors
import sys
from pathlib import Path
from tqdm import tqdm
import warnings
import gsw
from scipy.stats import pearsonr
import argparse
import os
import logging

CURRENT_SCRIPT = Path(__file__).resolve()
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')

project_root = CURRENT_SCRIPT.parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

warnings.filterwarnings('ignore')

def get_time_series_matrix(df, param, season_filter, saisuipoin=None):
    mask = df['season'] == season_filter
    if saisuipoin is not None:
        mask &= df['saisuipoin'] == saisuipoin
    
    subset = df.loc[mask, ['surveyyear', 'zettaicode', param]].copy()
    subset[param] = pd.to_numeric(subset[param], errors='coerce')
    
    matrix = subset.groupby(['surveyyear', 'zettaicode'])[param].mean().unstack()
    matrix.index = matrix.index.astype(int)
    matrix.index.name = 'year'
    
    return matrix

def compute_density_matrix(temp_matrix, salt_matrix, station_coords):
    density_matrix = pd.DataFrame(index=temp_matrix.index, columns=temp_matrix.columns, dtype=float)
    common_stations = temp_matrix.columns.intersection(salt_matrix.columns).intersection(station_coords.index)
    
    for stn in common_stations:
        lat = station_coords.loc[stn, 'latitude']
        lon = station_coords.loc[stn, 'longitude']
        
        t = temp_matrix[stn]
        s = salt_matrix[stn]
        
        valid = t.notna() & s.notna()
        if valid.sum() == 0:
            continue
        
        SA = gsw.SA_from_SP(s[valid], 0, lon, lat)
        CT = gsw.CT_from_t(SA, t[valid], 0)
        sigma0 = gsw.sigma0(SA, CT)
        
        density_matrix.loc[valid, stn] = sigma0.values
    
    density_matrix.index.name = 'year'
    return density_matrix.astype(float)

def calculate_pc_station_correlations(target_series, env_matrices, param_names, min_years=5):
    all_stations = set()
    for mat in env_matrices:
        all_stations.update(mat.columns)
    all_stations = sorted(list(all_stations))
    
    corr_records = []
    
    for stn in all_stations:
        row_corr = {'zettaicode': stn}
        row_pval = {'zettaicode': stn}
        row_n = {'zettaicode': stn}
        
        for mat, pname in zip(env_matrices, param_names):
            if stn not in mat.columns:
                row_corr[pname] = np.nan
                row_pval[pname + '_pval'] = np.nan
                row_n[pname + '_n'] = 0
                continue
            
            env_series = mat[stn].dropna()
            
            common_years = target_series.index.intersection(env_series.index)
            if len(common_years) >= min_years:
                if target_series.loc[common_years].std() == 0 or env_series.loc[common_years].std() == 0:
                    r, p = np.nan, np.nan
                else:
                    r, p = pearsonr(target_series.loc[common_years], env_series.loc[common_years])
                row_corr[pname] = r
                row_pval[pname + '_pval'] = p
                row_n[pname + '_n'] = len(common_years)
            else:
                row_corr[pname] = np.nan
                row_pval[pname + '_pval'] = np.nan
                row_n[pname + '_n'] = len(common_years)
        
        corr_records.append({**row_corr, **row_pval, **row_n})
        
    return pd.DataFrame(corr_records).set_index('zettaicode')

def create_correlation_map(corr_df, parameter, output_path, title_prefix, target_region="Tokyo Bay", output_prefix=None, merged_df=None):
    if merged_df is None:
        merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    
    if target_region in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        merged_df_region = merged_df[merged_df['watermass_name'] == target_region]
    else:
        merged_df_region = merged_df[merged_df['division'] == target_region]

    stations = merged_df_region[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    stations.index = stations.index.astype(str).str.zfill(8)
    corr_df.index = corr_df.index.astype(str).str.zfill(8)
    
    p_col = parameter + '_pval'
    if parameter not in corr_df.columns or p_col not in corr_df.columns:
        return
        
    plot_data = stations.join(corr_df[[parameter, p_col]], how='inner').dropna(subset=[parameter, p_col])

    if plot_data.empty:
        return

    extent = MappingConfig.get_dynamic_extent(target_region, plot_data=plot_data)
    extent_width = extent[1] - extent[0]
    zoom_factor = max(4.5 / extent_width, 1.0)
    fig_width, fig_height = MappingConfig.get_dynamic_figsize(extent, base_width=10)
    single_fig_height = fig_height + 1.4
    
    fig = plt.figure(figsize=(fig_width, single_fig_height))
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    ax.set_facecolor(MappingConfig.COLOR_OCEAN if hasattr(MappingConfig, 'COLOR_OCEAN') else 'lightblue')
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor=getattr(MappingConfig, 'COLOR_LAND', 'whitesmoke'), edgecolor='gray', zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
    land_boundary_file = "polbnda_jpn.shp" 
    if hasattr(MappingConfig, 'get_boundary_file'):
        land_boundary_file = MappingConfig.get_boundary_file(target_region)
    land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / land_boundary_file
    
    if land_boundary_path.exists():
        sis_land_boundary = gpd.read_file(land_boundary_path)
        if sis_land_boundary.crs != "EPSG:4326":
            sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")

        sis_land_boundary.plot(
            ax=ax,
            facecolor=getattr(MappingConfig, 'COLOR_LAND', 'whitesmoke'),
            edgecolor=getattr(MappingConfig, 'COLOR_LAND_EDGE', 'gray'),
            linewidth=MappingConfig.LINEWIDTH_LAND,
            transform=ccrs.PlateCarree(),
            zorder=MappingConfig.ZORDER_LAND
        )
    
    if hasattr(MappingConfig, 'apply_gridlines'):
        gl = MappingConfig.apply_gridlines(ax)
    
    colors = []
    sizes = []
    
    cmap = plt.get_cmap('coolwarm')
    norm = mcolors.Normalize(vmin=-1, vmax=1)
    
    for val, p_val in zip(plot_data[parameter], plot_data[p_col]):
        if p_val <= 0.001: size = 500
        elif p_val <= 0.01: size = 300
        elif p_val <= 0.05: size = 150
        else: size = 20
        sizes.append(size * zoom_factor)
        
        if val < -0.75: color = cmap(0.0)
        elif val < -0.5: color = cmap(0.15)
        elif val < -0.25: color = cmap(0.3)
        elif val < 0: color = cmap(0.45)
        elif val < 0.25: color = cmap(0.55)
        elif val < 0.5: color = cmap(0.7)
        elif val < 0.75: color = cmap(0.85)
        else: color = cmap(1.0)
        colors.append(color)

    sc = ax.scatter(
        plot_data['longitude'],
        plot_data['latitude'],
        c=colors,
        s=sizes,
        edgecolors='k',
        linewidths=0.5,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_PREDICTED,
        alpha=1
    )
    
    display_name = output_prefix if output_prefix else target_region
    plt.title(f"{title_prefix} vs {parameter.replace('_', ' ')} Correlation\n{display_name}", pad=20, fontsize=20, fontweight='bold')
    
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    ticks = [-1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0]
    
    cbar_ax = fig.add_axes([0.92, 0.15, 0.03, 0.7]) 
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation='vertical', ticks=ticks)
    cbar.set_label('Pearson Correlation (Red=Positive, Blue=Negative)', fontsize=14) 
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pc_name', required=True, help="e.g., PC1, PC2")
    parser.add_argument('--target_region', required=True, help="e.g., Tokyo Bay, Ise Bay")
    parser.add_argument('--output_prefix', required=False, help="e.g., Mikawa-Bay, Ise-Mikawa Bay")
    parser.add_argument('--start_year', type=int, required=True, help="e.g., 2013")
    parser.add_argument('--end_year', type=int, required=True, help="e.g., 2023")
    args = parser.parse_args()
    
    logging.info(f"Starting correlation analysis for {args.target_region} ({args.output_prefix}) {args.pc_name} {args.start_year}-{args.end_year}")
    
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))
    
    region_mapping = {
        "Tokyo Bay": "tokyo_bay",
        "Ise Bay": "ise_mikawa_bay",
        "Seto Inland Sea": "seto_inland_sea"
    }
    
    pc_score_region = region_mapping.get(args.target_region, args.target_region.lower().replace(' ', '_'))
    
    pc_scores_path = ProjectPaths.PROCESSED_DATA_DIR / 'step4_PCA_analysis' / 'process11_calculate_pca_explained_variance_per_bay_raw' / pc_score_region / f'{pc_score_region}_pc_scores.csv'
    
    if not pc_scores_path.exists():
        logging.error(f"PC scores file not found at {pc_scores_path}")
        return
        
    pc_scores_df = pd.read_csv(pc_scores_path, index_col=0)
    pc_scores_df.index = pc_scores_df.index.astype(int)
    pc_scores_df.index.name = 'year'
    
    if args.pc_name not in pc_scores_df.columns:
        logging.error(f"PC {args.pc_name} not found in {pc_scores_path}")
        return
        
    target_series = pc_scores_df.loc[args.start_year:args.end_year, args.pc_name]
    
    logging.info("Loading environmental data...")
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    # Filter for target_region
    merged_df = merged_df[merged_df['watermass_name'] == args.target_region].copy()
    
    if 'din2' not in merged_df.columns:
        merged_df['din2'] = merged_df['nh4n2'].fillna(0) + merged_df['no2n2'].fillna(0) + merged_df['no3n2'].fillna(0)
    if 'dip2' not in merged_df.columns:
        merged_df['dip2'] = merged_df['po4p2']

    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    station_coords = stations[['latitude', 'longitude']]
    
    logging.info("Building environmental & nutrient time series matrices...")
    env_matrices = []
    param_names = []
    
    # Environment
    wtemp_1_matrix = get_time_series_matrix(merged_df, 'wtemp', 'Summer', saisuipoin=1)
    wtemp_2_matrix = get_time_series_matrix(merged_df, 'wtemp', 'Summer', saisuipoin=2)
    salt2_1_matrix = get_time_series_matrix(merged_df, 'salt2', 'Summer', saisuipoin=1)
    salt2_2_matrix = get_time_series_matrix(merged_df, 'salt2', 'Summer', saisuipoin=2)
    wind_matrix = get_time_series_matrix(merged_df, 'fusoku', 'Summer')
    air_t_matrix = get_time_series_matrix(merged_df, 'temp', 'Winter')
    spring_chla_1_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Spring', saisuipoin=1)
    spring_chla_2_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Spring', saisuipoin=2)
    chla_1_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Summer', saisuipoin=1)
    chla_2_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Summer', saisuipoin=2)
    
    density_1_matrix = compute_density_matrix(wtemp_1_matrix, salt2_1_matrix, station_coords)
    density_2_matrix = compute_density_matrix(wtemp_2_matrix, salt2_2_matrix, station_coords)
    
    surface_depth_matrix = get_time_series_matrix(merged_df, 'saisuidept', 'Summer', saisuipoin=1)
    bottom_depth_matrix = get_time_series_matrix(merged_df, 'saisuidept', 'Summer', saisuipoin=2)
    
    depth_diff_matrix = bottom_depth_matrix - surface_depth_matrix
    depth_diff_matrix = depth_diff_matrix.replace(0, np.nan)
    stratification_matrix = (density_2_matrix - density_1_matrix) / depth_diff_matrix

    wtemp_1_matrix_w = get_time_series_matrix(merged_df, 'wtemp', 'Winter', saisuipoin=1)
    wtemp_2_matrix_w = get_time_series_matrix(merged_df, 'wtemp', 'Winter', saisuipoin=2)
    salt2_1_matrix_w = get_time_series_matrix(merged_df, 'salt2', 'Winter', saisuipoin=1)
    salt2_2_matrix_w = get_time_series_matrix(merged_df, 'salt2', 'Winter', saisuipoin=2)
    
    density_1_matrix_w = compute_density_matrix(wtemp_1_matrix_w, salt2_1_matrix_w, station_coords)
    density_2_matrix_w = compute_density_matrix(wtemp_2_matrix_w, salt2_2_matrix_w, station_coords)
    
    surface_depth_matrix_w = get_time_series_matrix(merged_df, 'saisuidept', 'Winter', saisuipoin=1)
    bottom_depth_matrix_w = get_time_series_matrix(merged_df, 'saisuidept', 'Winter', saisuipoin=2)
    
    depth_diff_matrix_w = bottom_depth_matrix_w - surface_depth_matrix_w
    depth_diff_matrix_w = depth_diff_matrix_w.replace(0, np.nan)
    winter_stratification_matrix = (density_2_matrix_w - density_1_matrix_w) / depth_diff_matrix_w
    
    env_mats = [
        wtemp_1_matrix, wtemp_2_matrix, salt2_1_matrix, salt2_2_matrix,
        density_1_matrix, density_2_matrix, stratification_matrix, winter_stratification_matrix,
        wind_matrix, air_t_matrix, spring_chla_1_matrix, spring_chla_2_matrix,
        chla_1_matrix, chla_2_matrix
    ]
    env_names = [
        'Summer_1_WTEMP', 'Summer_2_WTEMP', 'Summer_1_SALT2', 'Summer_2_SALT2',
        'Summer_1_DENSITY', 'Summer_2_DENSITY', 'Summer_Stratification', 'Winter_Stratification',
        'Summer_Wind_Speed', 'Winter_Air_Temp', 'Spring_1_CHLA', 'Spring_2_CHLA',
        'Summer_1_CHLA', 'Summer_2_CHLA'
    ]
    env_matrices.extend(env_mats)
    param_names.extend(env_names)
    
    # Nutrients
    nutrients = ['cod2', 'doc2', 'tn2', 'tp2', 'din2', 'dip2', 'nh4n2', 'no2n2', 'no3n2', 'po4p2']
    for nutr in nutrients:
        mat_s = get_time_series_matrix(merged_df, nutr, 'Summer', saisuipoin=1)
        env_matrices.append(mat_s)
        param_names.append(f'Summer_1_{nutr.upper()}')
        
        mat_b = get_time_series_matrix(merged_df, nutr, 'Summer', saisuipoin=2)
        env_matrices.append(mat_b)
        param_names.append(f'Summer_2_{nutr.upper()}')
        
    logging.info(f"Calculating {args.pc_name} correlations for {args.target_region} ({args.start_year}-{args.end_year})...")
    
    # Filter for matching years
    filtered_env_matrices = []
    for mat in env_matrices:
        valid_years = mat.index.intersection(target_series.index)
        filtered_env_matrices.append(mat.loc[valid_years])
    
    corr_df = calculate_pc_station_correlations(target_series, filtered_env_matrices, param_names)
    
    display_name = args.output_prefix if args.output_prefix else args.target_region
    prefix_str = display_name.replace(' ', '_').replace('-', '_')
    year_period = f"{args.start_year}-{args.end_year}"
    region_output_dir = OUTPUT_DIR / prefix_str / year_period
    region_output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_out_dir = PROCESSED_DATA_DIR / prefix_str / year_period
    csv_out_dir.mkdir(parents=True, exist_ok=True)
    csv_out = csv_out_dir / f"{prefix_str}_{args.pc_name}_{args.start_year}_{args.end_year}_correlations.csv"
    corr_df.to_csv(csv_out)
    logging.info(f"Saved correlation data to {csv_out}")
    
    logging.info(f"Generating maps for {display_name}...")
    
    for param in tqdm(param_names, desc=f"Mapping {display_name}"):
        if param not in corr_df.columns:
            continue
        safe_param = param.replace(' ', '_').replace('/', '_')
        output_path = region_output_dir / f"spatial_corr_map_env_{args.pc_name}_{safe_param}_{prefix_str}_{args.start_year}_{args.end_year}.png"
        create_correlation_map(corr_df, param, output_path, title_prefix=f"{args.pc_name} ({args.start_year}-{args.end_year})", target_region=args.target_region, output_prefix=display_name, merged_df=merged_df)
        
    logging.info("Finished generating all maps.")

if __name__ == '__main__':
    main()

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

# Add project root to sys.path to import utils
project_root = Path(__file__).resolve().parents[1]
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

def calculate_raw_station_correlations(target_matrix, env_matrices, param_names, min_years=5):
    all_stations = set(target_matrix.columns)
    for mat in env_matrices:
        all_stations.update(mat.columns)
    all_stations = sorted(list(all_stations))
    
    corr_records = []
    
    for stn in all_stations:
        row_corr = {'zettaicode': stn}
        row_pval = {'zettaicode': stn}
        row_n = {'zettaicode': stn}
        
        if stn not in target_matrix.columns:
            # no target DO data for this station
            continue
            
        target_series = target_matrix[stn].dropna()
        if len(target_series) < min_years:
            continue
            
        for mat, pname in zip(env_matrices, param_names):
            if stn not in mat.columns:
                row_corr[pname] = np.nan
                row_pval[pname + '_pval'] = np.nan
                row_n[pname + '_n'] = 0
                continue
            
            env_series = mat[stn].dropna()
            
            common_years = target_series.index.intersection(env_series.index)
            if len(common_years) >= min_years:
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

def create_correlation_map(corr_df, parameter, output_path, title_prefix, target_region="Seto Inland Sea", merged_df=None):
    # Filter data first to get data bounds
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

    # 1. Calculation for Figure Dimensions (Maintaining Aspect Ratio)
    water_boundary_files = {
        'Seto Inland Sea': 'sea_area_mask_sis_simplified.shp',
        'Tokyo Bay': 'sea_area_mask_Tokyo.shp',
        'Ise Bay': 'sea_area_mask_Ise.shp'
    }
    water_boundary_file = water_boundary_files.get(target_region, 'sea_area_mask_sis_simplified.shp')
    water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / water_boundary_file
    
    # Use dynamic extent with 0.2 buffer
    minx, maxx = plot_data['longitude'].min(), plot_data['longitude'].max()
    miny, maxy = plot_data['latitude'].min(), plot_data['latitude'].max()
    buffer = 0.2
    extent = [minx - buffer, maxx + buffer, miny - buffer, maxy + buffer]

    aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])
    
    if aspect_ratio > 1:
        fig_height = 10
        fig_width = fig_height / aspect_ratio
    else:
        fig_width = 10
        fig_height = fig_width * aspect_ratio
        
    single_fig_height = fig_height + 1.4
    
    # 2. Base Figure Setup
    fig = plt.figure(figsize=(fig_width, single_fig_height))
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    ax.set_facecolor(MappingConfig.COLOR_OCEAN if hasattr(MappingConfig, 'COLOR_OCEAN') else 'lightblue')
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor=getattr(MappingConfig, 'COLOR_LAND', 'whitesmoke'), edgecolor='gray', zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
    # 3. Add High-Res Coastlines (Land Boundary)
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
    
    # 4. Add Gridlines
    if hasattr(MappingConfig, 'apply_gridlines'):
        gl = MappingConfig.apply_gridlines(ax)
    
    # 5. Determine Colors and Sizes
    colors = []
    sizes = []
    
    cmap = plt.get_cmap('coolwarm')
    norm = mcolors.Normalize(vmin=-1, vmax=1)
    
    for val, p_val in zip(plot_data[parameter], plot_data[p_col]):
        if p_val <= 0.001: size = 500
        elif p_val <= 0.01: size = 300
        elif p_val <= 0.05: size = 150
        else: size = 20
        sizes.append(size)
        
        if val < -0.75: color = cmap(0.0)
        elif val < -0.5: color = cmap(0.15)
        elif val < -0.25: color = cmap(0.3)
        elif val < 0: color = cmap(0.45)
        elif val < 0.25: color = cmap(0.55)
        elif val < 0.5: color = cmap(0.7)
        elif val < 0.75: color = cmap(0.85)
        else: color = cmap(1.0)
        colors.append(color)

    # 6. Scatter Plot
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
    
    # 7. Add Title and Colorbar
    plt.title(f"{title_prefix} vs {parameter.replace('_', ' ')} Correlation\n{target_region}", pad=20, fontsize=20, fontweight='bold')
    
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
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))
    
    print("Loading data...")
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    # Calculate DIN2 and DIP2 if not present
    if 'din2' not in merged_df.columns:
        merged_df['din2'] = merged_df['nh4n2'].fillna(0) + merged_df['no2n2'].fillna(0) + merged_df['no3n2'].fillna(0)
    if 'dip2' not in merged_df.columns:
        merged_df['dip2'] = merged_df['po4p2']

    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    station_coords = stations[['latitude', 'longitude']]
    
    print("Building DO time series matrix (Summer Bottom)...")
    do_matrix = get_time_series_matrix(merged_df, 'do_2', 'Summer', saisuipoin=2)
    
    print("Building environmental & nutrient time series matrices...")
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
        
    print("Calculating raw DO correlations for all stations...")
    corr_df = calculate_raw_station_correlations(do_matrix, env_matrices, param_names)
    
    output_dir = ProjectPaths.FIGURES_DIR / 'step0_sandbox' / '65_spatial_correlation_map_raw_DO'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the correlation dataframe for reference
    corr_df.to_csv(output_dir / "raw_do_correlations_all_stations.csv")
    print(f"Saved correlation data to {output_dir / 'raw_do_correlations_all_stations.csv'}")
    
    regions = ['Seto Inland Sea', 'Tokyo Bay', 'Ise Bay']
    for region in regions:
        print(f"Generating maps for {region}...")
        region_output_dir = output_dir / region.replace(' ', '_')
        region_output_dir.mkdir(parents=True, exist_ok=True)
        
        for param in tqdm(param_names, desc=f"Mapping {region}"):
            if param not in corr_df.columns:
                continue
            safe_param = param.replace(' ', '_').replace('/', '_')
            region_str = region.replace(" ", "_")
            data_type = 'env' if param in env_names else 'nutr'
            output_path = region_output_dir / f"spatial_corr_map_{data_type}_RawDO_{safe_param}_{region_str}_Summer_bottom.png"
            create_correlation_map(corr_df, param, output_path, title_prefix="Summer Bottom DO", target_region=region, merged_df=merged_df)
            
    print("Finished generating all maps.")

if __name__ == '__main__':
    main()

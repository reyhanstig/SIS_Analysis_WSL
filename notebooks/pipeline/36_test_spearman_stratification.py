import pandas as pd
import numpy as np
import gsw
from scipy.stats import spearmanr
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.colors as mcolors
import sys
from pathlib import Path
from tqdm import tqdm

# Add project root to sys.path to import scripts.paths
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from scripts.paths import ProjectPaths
from scripts.mapping_config import MappingConfig

# Apply the global project style
plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))

def get_time_series_matrix(df, param, saisuipoin=None):
    mask = df['season'] == 'Summer'
    if saisuipoin is not None:
        mask &= df['saisuipoin'] == saisuipoin
    subset = df.loc[mask, ['surveyyear', 'zettaicode', param]].copy()
    subset[param] = pd.to_numeric(subset[param], errors='coerce')
    matrix = subset.groupby(['surveyyear', 'zettaicode'])[param].mean().unstack()
    matrix.index = matrix.index.astype(int)
    return matrix

def compute_density_matrix(temp_matrix, salt_matrix, station_coords):
    density_matrix = pd.DataFrame(index=temp_matrix.index, columns=temp_matrix.columns, dtype=float)
    common_stations = temp_matrix.columns.intersection(salt_matrix.columns).intersection(station_coords.index)
    for stn in common_stations:
        lat, lon = station_coords.loc[stn, ['latitude', 'longitude']]
        t, s = temp_matrix[stn], salt_matrix[stn]
        valid = t.notna() & s.notna()
        if valid.any():
            SA = gsw.SA_from_SP(s[valid], 0, lon, lat)
            CT = gsw.CT_from_t(SA, t[valid], 0)
            density_matrix.loc[valid, stn] = gsw.sigma0(SA, CT)
    return density_matrix.astype(float)

def main():
    # 1. Load Data
    print("Loading data...")
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    subset_dir = ProjectPaths.get_subset_dir('Summer', 'bottom')
    pca_scores = pd.read_csv(subset_dir / 'pca_scores.csv', index_col=0)
    pca_scores.index = pca_scores.index.astype(int)
    
    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    stations.index = stations.index.astype(str).str.zfill(8)

    # 2. Process Stratification
    print("Building stratification matrix...")
    temp_1 = get_time_series_matrix(merged_df, 'wtemp', 1)
    temp_2 = get_time_series_matrix(merged_df, 'wtemp', 2)
    salt_1 = get_time_series_matrix(merged_df, 'salt2', 1)
    salt_2 = get_time_series_matrix(merged_df, 'salt2', 2)
    dens_1 = compute_density_matrix(temp_1, salt_1, stations)
    dens_2 = compute_density_matrix(temp_2, salt_2, stations)
    depth_1 = get_time_series_matrix(merged_df, 'saisuidept', 1)
    depth_2 = get_time_series_matrix(merged_df, 'saisuidept', 2)
    strat_matrix = (dens_2 - dens_1) / (depth_2 - depth_1).replace(0, np.nan)

    # 3. Calculate Spearman Correlation for PC2
    print("Calculating Spearman correlation for PC2 vs Stratification...")
    pc2 = pca_scores['PC2']
    corr_results = []
    for stn in strat_matrix.columns:
        s_env = strat_matrix[stn].dropna()
        common_years = pc2.index.intersection(s_env.index)
        if len(common_years) >= 5:
            r, p = spearmanr(pc2.loc[common_years], s_env.loc[common_years])
            corr_results.append({'zettaicode': stn, 'r': r, 'p': p})
    
    plot_df = pd.DataFrame(corr_results).set_index('zettaicode')
    plot_data = stations.join(plot_df, how='inner').dropna()

    # 4. Plotting
    print("Generating map...")
    water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp"
    sis_water_boundary = gpd.read_file(water_boundary_path).to_crs("EPSG:4326")
    bounds = sis_water_boundary.total_bounds
    extent = [bounds[0] + 0.1, bounds[2] + 0.1, bounds[1] - 0, bounds[3] + 0.2]
    
    aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])
    fig_width = 10
    fig_height = (fig_width * aspect_ratio) + 1.2
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    
    ax.add_feature(cfeature.LAND, facecolor='whitesmoke', edgecolor='gray', zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
    # High-res land
    land_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary.shp"
    gpd.read_file(land_path).to_crs("EPSG:4326").plot(
        ax=ax, facecolor='whitesmoke', edgecolor='gray', linewidth=MappingConfig.LINEWIDTH_LAND, zorder=MappingConfig.ZORDER_LAND
    )
    
    ax.gridlines(draw_labels=True, linestyle='--', color='gray', alpha=0.4, linewidth=0.5, zorder=MappingConfig.ZORDER_GRIDLINES)
    
    cmap = plt.get_cmap('coolwarm')
    norm = mcolors.Normalize(vmin=-1, vmax=1)
    
    colors = [cmap(norm(r)) for r in plot_data['r']]
    sizes = [500 if p <= 0.001 else 300 if p <= 0.01 else 150 if p <= 0.05 else 20 for p in plot_data['p']]
    
    ax.scatter(plot_data['longitude'], plot_data['latitude'], c=colors, s=sizes, edgecolors='k', linewidths=0.5, transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_PREDICTED)
    
    plt.title("PC2 vs Summer Stratification Spearman Correlation", pad=20, fontsize=20, fontweight='bold')
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar_ax = fig.add_axes([0.92, 0.15, 0.03, 0.7])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation='vertical', ticks=[-1.0, -0.5, 0, 0.5, 1.0])
    cbar.set_label('Spearman Correlation (r)', fontsize=14)
    
    output_path = ProjectPaths.FIGURES_DIR / "seasonal_plots" / "environment_correlations" / "PC2_Summer_Stratification_Spearman.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Test map saved to {output_path}")

if __name__ == '__main__':
    main()

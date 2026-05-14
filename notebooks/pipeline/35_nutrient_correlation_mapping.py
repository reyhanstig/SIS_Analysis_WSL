import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import pandas as pd
import numpy as np
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

def create_correlation_map(corr_df, parameter, output_path, pc_name):
    """
    Creates a single plot showing correlation between PC scores and a nutrient parameter.
    Circle color indicates correlation value (r) and size indicates significance (p-value).
    """
    # 1. Calculation for Figure Dimensions (Maintaining Aspect Ratio)
    # Get extent from water boundary per reports/SIS_mapping_standard.md
    water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp"
    sis_water_boundary = gpd.read_file(water_boundary_path)
    if sis_water_boundary.crs != "EPSG:4326":
        sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
    bounds = sis_water_boundary.total_bounds
    
    # Standard extent: [xmin, xmax, ymin, ymax]
    extent = [bounds[0] + 0.1, bounds[2] + 0.1, bounds[1] - 0, bounds[3] + 0.2]
    
    aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])
    fig_width = 10
    single_fig_height = (fig_width * aspect_ratio) + 1.2  # Buffer for title and labels
    
    # 2. Base Figure Setup
    fig = plt.figure(figsize=(fig_width, single_fig_height))
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor='whitesmoke', edgecolor='gray', zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
    # 3. Add High-Res Coastlines (Land Boundary)
    land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary.shp"
    sis_land_boundary = gpd.read_file(land_boundary_path)

    if sis_land_boundary.crs != "EPSG:4326":
        sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")

    sis_land_boundary.plot(
        ax=ax,
        facecolor='whitesmoke',
        edgecolor='gray',
        linewidth=MappingConfig.LINEWIDTH_LAND,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_LAND
    )
    
    # 4. Add Gridlines
    gl = ax.gridlines(draw_labels=True, linestyle='--', color='gray', alpha=0.4, 
                      linewidth=0.5, zorder=MappingConfig.ZORDER_GRIDLINES)
    gl.top_labels = False
    gl.right_labels = False
    
    # 4. Prepare Data for Plotting
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    stations.index = stations.index.astype(str).str.zfill(8)
    corr_df.index = corr_df.index.astype(str).str.zfill(8)
    
    # Column mapping
    p_col = parameter + '_pval'
    
    # Inner join to only map available stations
    plot_data = stations.join(corr_df[[parameter, p_col]], how='inner').dropna(subset=[parameter, p_col])
    
    # Define mapping rules for correlation value -> colors and significance -> sizes
    colors = []
    sizes = []
    
    # using coolwarm colormap: from blue (negative) to red (positive)
    cmap = plt.get_cmap('coolwarm')
    norm = mcolors.Normalize(vmin=-1, vmax=1)
    
    for val, p_val in zip(plot_data[parameter], plot_data[p_col]):
        
        # 1. Size based on significance (p-value thresholds)
        if p_val <= 0.001:
            size = 500  # ***
        elif p_val <= 0.01:
            size = 300  # **
        elif p_val <= 0.05:
            size = 150   # *
        else:
            size = 20   # ns
            
        sizes.append(size)
        
        # 2. Colors based on correlation value (r) - discrete 8 bins
        if val < -0.75:
            color = cmap(0.0)
        elif val < -0.5:
            color = cmap(0.15)
        elif val < -0.25:
            color = cmap(0.3)
        elif val < 0:
            color = cmap(0.45)
        elif val < 0.25:
            color = cmap(0.55)
        elif val < 0.5:
            color = cmap(0.7)
        elif val < 0.75:
            color = cmap(0.85)
        else:
            color = cmap(1.0)
            
        colors.append(color)

    # 5. Scatter Plot
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
    plt.title(f"{pc_name} vs {parameter.replace('_', ' ')} Correlation", pad=20, fontsize=20, fontweight='bold')
    
    # 7a. Colorbar for Correlation values
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
    season = 'Summer'
    layer = 'bottom'
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    
    pc1_corr_path = subset_dir / 'pca_nutr_corr_pc1.csv'
    pc2_corr_path = subset_dir / 'pca_nutr_corr_pc2.csv'
    
    if not pc1_corr_path.exists() or not pc2_corr_path.exists():
        print(f"Error: nutrient correlation files not found in {subset_dir}")
        print("  Run 35_DO_PCA_nutr_corr.py first to generate them.")
        return
        
    df_pc1 = pd.read_csv(pc1_corr_path, index_col=0)
    df_pc2 = pd.read_csv(pc2_corr_path, index_col=0)
    
    ProjectPaths.ensure_directories()
    output_dir = ProjectPaths.FIGURES_DIR / "seasonal_plots" / "nutrient_correlations"
    
    # Process both PCs
    for pc_name, df_pc in [("PC1", df_pc1), ("PC2", df_pc2)]:
        print(f"\nProcessing {pc_name} nutrient correlations...")
        # Get nutrient parameter names: only base columns that have a matching _pval column
        parameters = [c for c in df_pc.columns if f"{c}_pval" in df_pc.columns]
        for param in tqdm(parameters, desc=f"Mapping {pc_name}"):
            # param is like 'Summer_1_COD2'
            output_path = output_dir / f"{pc_name}_{param}.png"
            create_correlation_map(df_pc, param, output_path, pc_name)
    
    print("\nAll nutrient correlation maps generated successfully.")

if __name__ == '__main__':
    main()

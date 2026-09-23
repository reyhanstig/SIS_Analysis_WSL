#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import gsw
import sys
from pathlib import Path
import os
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geopandas as gpd

# Ensure we can import from 'utils' directory
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from utils.data_loader import load_and_process_data
from utils.mapping_config import MappingConfig

# Apply global project style
plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))

# Define the new dedicated output directory in the windows symlink
output_dir = ProjectPaths.FIGURES_DIR / "step0_sandbox" / "73a_explore_pc_env_relationship"
output_dir.mkdir(parents=True, exist_ok=True)
print(f"Output directory set to: {output_dir}")

# 1. Load PC Scores and EOFs for Tokyo Bay
pca_dir = ProjectPaths.PROCESSED_DATA_DIR / 'step4_PCA_analysis' / 'process11_calculate_pca_explained_variance_per_bay_raw' / 'tokyo_bay'
pc_scores = pd.read_csv(pca_dir / 'tokyo_bay_pc_scores.csv', index_col=0)
eof_df = pd.read_csv(pca_dir / 'tokyo_bay_eof_patterns.csv')
eof_df['Station_ID'] = eof_df['Station_ID'].astype(str).str.zfill(8)

var_df = pd.read_csv(pca_dir / 'tokyo_bay_pca_variance.csv')
var_pct_dict = dict(zip(var_df['PC'], var_df['Variance_Pct']))

# 2. Load environmental data
merged_gdf = load_and_process_data(force_reload=False)
merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

# Calculate density
merged_gdf['density'] = gsw.rho(pd.to_numeric(merged_gdf['salt'], errors='coerce'), 
                                pd.to_numeric(merged_gdf['wtemp'], errors='coerce'), 0) - 1000

# Define parameters to plot
params = [
    {'pc': 'PC1', 'name': 'Summer 1 Density', 'season': 'Summer', 'layer': 1, 'col': 'density', 'unit': 'kg/m³'},
    {'pc': 'PC1', 'name': 'Summer 2 DOC', 'season': 'Summer', 'layer': 2, 'col': 'doc', 'unit': 'mg/L'},
    {'pc': 'PC1', 'name': 'Summer 2 TN', 'season': 'Summer', 'layer': 2, 'col': 'tn', 'unit': 'mg/L'},
    {'pc': 'PC2', 'name': 'Summer 2 wtemp', 'season': 'Summer', 'layer': 2, 'col': 'wtemp', 'unit': '°C'},
    {'pc': 'PC2', 'name': 'Summer 1 DIP', 'season': 'Summer', 'layer': 1, 'col': 'po4p', 'unit': 'mg/L'},
    {'pc': 'PC2', 'name': 'Summer 1 PO4-P', 'season': 'Summer', 'layer': 1, 'col': 'po4p', 'unit': 'mg/L'}
]

# Determine dynamic tick years matching process12
first_year = pc_scores.index[0]
last_year = pc_scores.index[-1]
target_type = type(first_year)
mid_ticks = [target_type(y) for y in range(1985, 2021, 5) if target_type(y) in pc_scores.index]
tick_years = sorted(list(set([first_year] + mid_ticks + [last_year])), key=lambda x: int(x))

division = 'Tokyo Bay'
plotted_maps = set()

for p in params:
    print(f"\n{'='*50}\nProcessing {p['name']}\n{'='*50}")
    
    pc_var = var_pct_dict[p['pc']]
    pc_num = p['pc'][-1]
    
    # Get top 10 contributing stations for this PC
    eof_df[f'abs_EOF{pc_num}'] = eof_df[f'EOF{pc_num}'].abs()
    top10_stations = eof_df.sort_values(f'abs_EOF{pc_num}', ascending=False).head(10)['Station_ID'].tolist()
    
    # Filter data for the specific season and layer
    p_data = merged_gdf[(merged_gdf['season'] == p['season']) & 
                        (merged_gdf['saisuipoin'] == p['layer']) &
                        (merged_gdf['zettaicode'].isin(top10_stations))].copy()
    
    p_data[p['col']] = pd.to_numeric(p_data[p['col']], errors='coerce')
    
    # Create plot with same layout as process12
    fig, ax1 = plt.subplots(figsize=(10, 5))
    
    # Plot PC on the primary y-axis
    ax1.plot(pc_scores.index, pc_scores[p['pc']], marker='o', label=f'{p["pc"]} ({pc_var:.1f}%)', color='tab:blue')
    ax1.axhline(y=0, color='red', linestyle='--', alpha=0.7)
    ax1.set_xlabel('Year')
    ax1.set_ylabel(f'{p["pc"]} Score')
    ax1.set_title(f'Tokyo Bay: {p["pc"]} and {p["name"]}', fontsize=20, fontweight='bold')
    
    # Tick settings matching process12
    ax1.set_xticks(tick_years)
    ax1.tick_params(axis='x', rotation=45)
    ax1.grid(True, linestyle='--', alpha=0.6)
    
    # Create secondary y-axis for environmental parameter
    ax2 = ax1.twinx()
    
    # Plot top 10 stations
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    for i, st in enumerate(top10_stations):
        st_data = p_data[p_data['zettaicode'] == st].groupby('surveyyear')[p['col']].mean().reset_index()
        if not st_data.empty:
            ax2.plot(st_data['surveyyear'], st_data[p['col']], marker='^', markersize=4, alpha=0.5, 
                     color=colors[i], label=f'St. {st}', linestyle=':')
            
    ax2.set_ylabel(f'{p["name"]} [{p["unit"]}]')
    
    # Legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    ax1.legend(lines1, labels1, loc='upper left', fontsize=12)
    
    # Save the figure
    safe_name = p['name'].replace(' ', '_').lower()
    fig_out = output_dir / f"tokyo_bay_{p['pc'].lower()}_{safe_name}_top10_ts.png"
    plt.tight_layout()
    plt.savefig(fig_out, bbox_inches='tight', dpi=300)
    print(f"Saved figure to: {fig_out}")
    
    # Plot spatial map for this PC if not plotted yet
    if p['pc'] not in plotted_maps:
        station_coords = merged_gdf[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
        top10_eof = eof_df[eof_df['Station_ID'].isin(top10_stations)].set_index('Station_ID')
        
        plot_data_map = station_coords.loc[top10_eof.index].copy()
        plot_data_map['EOF'] = top10_eof[f'EOF{pc_num}'].values
        
        map_extent = MappingConfig.get_dynamic_extent(division, plot_data=plot_data_map)
        fig_width, fig_height = MappingConfig.get_dynamic_figsize(map_extent, base_width=10)
        
        fig_map, ax_map = plt.subplots(figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})
        ax_map.set_facecolor(MappingConfig.COLOR_OCEAN)
        ax_map.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
        ax_map.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
        
        land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Tokyobay_boundary.shp"
        if land_boundary_path.exists():
            land_boundary = gpd.read_file(land_boundary_path).to_crs("EPSG:4326")
            land_boundary.plot(ax=ax_map, facecolor=MappingConfig.COLOR_LAND, edgecolor=MappingConfig.COLOR_LAND_EDGE, 
                               linewidth=MappingConfig.LINEWIDTH_LAND, transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_LAND)
        
        vmax = max(abs(plot_data_map['EOF'].min()), abs(plot_data_map['EOF'].max()))
        zoom_factor = max(4.5 / (map_extent[1] - map_extent[0]), 1.0)
        
        sc = ax_map.scatter(
            plot_data_map['longitude'], plot_data_map['latitude'], c=plot_data_map['EOF'], cmap='coolwarm',
            vmin=-vmax, vmax=vmax, s=np.maximum(abs(plot_data_map['EOF']) * 800 * zoom_factor, 50 * zoom_factor), 
            edgecolors='k', linewidths=0.5, transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_OBSERVATIONS
        )
        
        for idx, row in plot_data_map.iterrows():
            ax_map.text(row['longitude'] + 0.005, row['latitude'] + 0.005, f'St. {idx}', 
                    transform=ccrs.PlateCarree(), fontsize=9, fontweight='bold', zorder=MappingConfig.ZORDER_OBSERVATIONS+1)
        
        MappingConfig.apply_gridlines(ax_map)
        ax_map.set_extent(map_extent, crs=ccrs.PlateCarree())
        ax_map.set_title(f'{division}: Top 10 Stations {p["pc"]} Spatial Pattern ({pc_var:.1f}%)', pad=15)
        
        cbar_ax = fig_map.add_axes([0.25, 0.05, 0.5, 0.03])
        fig_map.colorbar(sc, cax=cbar_ax, orientation='horizontal').set_label('EOF Weight')
        
        map_out = output_dir / f"tokyo_bay_{p['pc'].lower()}_top10_eof_map.png"
        plt.savefig(map_out, bbox_inches='tight', dpi=300)
        print(f"Saved map to: {map_out}")
        
        plotted_maps.add(p['pc'])

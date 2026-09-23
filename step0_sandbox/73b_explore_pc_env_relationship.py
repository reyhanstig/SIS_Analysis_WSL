#!/usr/bin/env python
# coding: utf-8

# # 73b: Explore PC and Environmental Factor Relationship (Significant Stations)
# 
# This notebook explores the relationship between Tokyo Bay PC1 and environmental factors:
# - Summer 1 Density
# - Summer 2 DOC
# - Summer 2 TN
# 
# For each parameter, we plot the time-series graph and spatial map of the **significant contributing stations** for PC1 based on correlation analysis (p <= 0.05).

# In[ ]:


# --- 1. Imports ---
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


# ## 2. Output Directory Setup

# In[ ]:


# Define the new dedicated output directory in the windows symlink
output_dir = ProjectPaths.FIGURES_DIR / "step0_sandbox" / "73b_explore_pc_env_relationship"
output_dir.mkdir(parents=True, exist_ok=True)
print(f"Output directory set to: {output_dir}")


# ## 3. Data Loading

# In[ ]:


# 1. Load PC Scores and EOFs for Tokyo Bay
pca_dir = ProjectPaths.PROCESSED_DATA_DIR / 'step4_PCA_analysis' / 'process11_calculate_pca_explained_variance_per_bay_raw' / 'tokyo_bay'
pc_scores = pd.read_csv(pca_dir / 'tokyo_bay_pc_scores.csv', index_col=0)
eof_df = pd.read_csv(pca_dir / 'tokyo_bay_eof_patterns.csv')
eof_df['Station_ID'] = eof_df['Station_ID'].astype(str).str.zfill(8)
tb_stations = eof_df['Station_ID'].tolist()

var_df = pd.read_csv(pca_dir / 'tokyo_bay_pca_variance.csv')
var_pct_dict = dict(zip(var_df['PC'], var_df['Variance_Pct']))

# 2. Load environmental data
merged_gdf = load_and_process_data(force_reload=False)
merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

# Calculate density
merged_gdf['density'] = gsw.rho(pd.to_numeric(merged_gdf['salt'], errors='coerce'), 
                                pd.to_numeric(merged_gdf['wtemp'], errors='coerce'), 0) - 1000


# ## 4. Plotting Time Series and Spatial Maps

# In[ ]:


# Define parameters to plot
params = [
    {'pc': 'PC1', 'name': 'Summer 1 Density', 'season': 'Summer', 'layer': 1, 'col': 'density', 'unit': 'kg/m³', 'data_type': 'env', 'param_str': 'Summer_1_DENSITY'},
    {'pc': 'PC1', 'name': 'Summer 2 DOC', 'season': 'Summer', 'layer': 2, 'col': 'doc', 'unit': 'mg/L', 'data_type': 'nutr', 'param_str': 'Summer_2_DOC2'},
    {'pc': 'PC1', 'name': 'Summer 2 TN', 'season': 'Summer', 'layer': 2, 'col': 'tn', 'unit': 'mg/L', 'data_type': 'nutr', 'param_str': 'Summer_2_TN2'},
    {'pc': 'PC2', 'name': 'Summer 2 wtemp', 'season': 'Summer', 'layer': 2, 'col': 'wtemp', 'unit': '°C', 'data_type': 'env', 'param_str': 'Summer_2_WTEMP'},
    {'pc': 'PC2', 'name': 'Summer 1 DIP', 'season': 'Summer', 'layer': 1, 'col': 'po4p', 'unit': 'mg/L', 'data_type': 'nutr', 'param_str': 'Summer_1_DIP2'},
    {'pc': 'PC2', 'name': 'Summer 1 PO4-P', 'season': 'Summer', 'layer': 1, 'col': 'po4p', 'unit': 'mg/L', 'data_type': 'nutr', 'param_str': 'Summer_1_PO4P2'}
]

# Determine dynamic tick years matching process12
first_year = pc_scores.index[0]
last_year = pc_scores.index[-1]
target_type = type(first_year)
mid_ticks = [target_type(y) for y in range(1985, 2021, 5) if target_type(y) in pc_scores.index]
tick_years = sorted(list(set([first_year] + mid_ticks + [last_year])), key=lambda x: int(x))

division = 'Tokyo Bay'
subset_dir = ProjectPaths.get_subset_dir('Summer', 'bottom')

for p in params:
    print(f"\n{'='*50}\nProcessing {p['name']}\n{'='*50}")
    
    pc_var = var_pct_dict[p['pc']]
    
    # 1. Identify significant stations based on correlation
    corr_file = subset_dir / f"pca_{p['data_type']}_corr_{p['pc'].lower()}.csv"
    df_corr = pd.read_csv(corr_file, index_col=0, dtype={0: str})
    df_corr.index = df_corr.index.str.zfill(8)
    
    # Filter for Tokyo Bay stations only
    df_corr = df_corr[df_corr.index.isin(tb_stations)]
    
    pval_col = f"{p['param_str']}_pval"
    
    # Significant if pval <= 0.05 and |r| > 0
    sig_df = df_corr[(df_corr[pval_col] <= 0.05) & (df_corr[p['param_str']].abs() > 0)]
    sig_stations = sig_df.index.tolist()
    
    print(f"Significant stations for {p['name']}: {sig_stations}")
    
    if not sig_stations:
        print(f"No significant stations found for {p['name']}. Skipping plot.")
        continue
        
    # 2. Filter raw data for the specific season and layer
    p_data = merged_gdf[(merged_gdf['season'] == p['season']) & 
                        (merged_gdf['saisuipoin'] == p['layer']) &
                        (merged_gdf['zettaicode'].isin(sig_stations))].copy()
    
    p_data[p['col']] = pd.to_numeric(p_data[p['col']], errors='coerce')
    
    # ---------------------------------------------------------
    # PLOT TIME SERIES
    # ---------------------------------------------------------
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
    
    # Plot significant stations
    for i, st in enumerate(sig_stations):
        st_data = p_data[p_data['zettaicode'] == st].groupby('surveyyear')[p['col']].mean().reset_index()
        if not st_data.empty:
            # Color based on whether correlation is positive or negative
            r_val = sig_df.loc[st, p['param_str']]
            line_color = 'red' if r_val > 0 else 'blue'
            ax2.plot(st_data['surveyyear'], st_data[p['col']], marker='^', markersize=4, alpha=0.5, 
                     color=line_color, label=f'St. {st} (r={r_val:.2f})', linestyle=':')
            
    ax2.set_ylabel(f'{p["name"]} [{p["unit"]}]')
    
    # Legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    ax1.legend(lines1, labels1, loc='upper left', fontsize=12)
    
    safe_name = p['name'].replace(' ', '_').lower()
    fig_out_ts = output_dir / f"tokyo_bay_{p['pc'].lower()}_{safe_name}_sig_ts.png"
    plt.tight_layout()
    plt.savefig(fig_out_ts, bbox_inches='tight', dpi=300)
    print(f"Saved TS figure to: {fig_out_ts}")
    
    # ---------------------------------------------------------
    # PLOT SPATIAL MAP
    # ---------------------------------------------------------
    station_coords = merged_gdf[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    sig_eof = eof_df[eof_df['Station_ID'].isin(sig_stations)].set_index('Station_ID')
    
    plot_data = station_coords.loc[sig_eof.index].copy()
    plot_data['EOF'] = sig_eof[f"EOF{p['pc'][-1]}"].values
    
    map_extent = MappingConfig.get_dynamic_extent(division, plot_data=plot_data)
    fig_width, fig_height = MappingConfig.get_dynamic_figsize(map_extent, base_width=10)
    
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
    land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Tokyobay_boundary.shp"
    if land_boundary_path.exists():
        land_boundary = gpd.read_file(land_boundary_path).to_crs("EPSG:4326")
        land_boundary.plot(ax=ax, facecolor=MappingConfig.COLOR_LAND, edgecolor=MappingConfig.COLOR_LAND_EDGE, 
                           linewidth=MappingConfig.LINEWIDTH_LAND, transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_LAND)
    
    vmax = max(abs(plot_data['EOF'].min()), abs(plot_data['EOF'].max())) if not plot_data.empty else 1.0
    zoom_factor = max(4.5 / (map_extent[1] - map_extent[0]), 1.0)
    
    if not plot_data.empty:
        sc = ax.scatter(
            plot_data['longitude'], plot_data['latitude'], c=plot_data['EOF'], cmap='coolwarm',
            vmin=-vmax, vmax=vmax, s=np.maximum(abs(plot_data['EOF']) * 800 * zoom_factor, 50 * zoom_factor), 
            edgecolors='k', linewidths=0.5, transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_OBSERVATIONS
        )
        
        for idx, row in plot_data.iterrows():
            ax.text(row['longitude'] + 0.005, row['latitude'] + 0.005, f'St. {idx}', 
                    transform=ccrs.PlateCarree(), fontsize=9, fontweight='bold', zorder=MappingConfig.ZORDER_OBSERVATIONS+1)
        
        cbar_ax = fig.add_axes([0.25, 0.05, 0.5, 0.03])
        fig.colorbar(sc, cax=cbar_ax, orientation='horizontal').set_label('EOF Weight')
    
    MappingConfig.apply_gridlines(ax)
    ax.set_extent(map_extent, crs=ccrs.PlateCarree())
    ax.set_title(f'{division}: {p["name"]} Sig Stations {p["pc"]} Map ({pc_var:.1f}%)', pad=15)
    
    fig_out_map = output_dir / f"tokyo_bay_{p['pc'].lower()}_{safe_name}_sig_map.png"
    plt.savefig(fig_out_map, bbox_inches='tight', dpi=300)
    print(f"Saved Map figure to: {fig_out_map}")


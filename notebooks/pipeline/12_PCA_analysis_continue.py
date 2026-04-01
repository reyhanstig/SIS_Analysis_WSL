# -*- coding: utf-8 -*-
# Auto-generated from: 12_PCA_analysis_continue.ipynb
# Generated on: 2026-03-12 16:35:21
# This script was converted from a Jupyter Notebook.
# Markdown cells have been converted to comments.

# # PCA Correlation Analysis
#
# This notebook analyzes the correlations between Principal Component (PC) scores and environmental factors (SST, SSS, SBT, SBS).
#
# ## Objectives
# 1. Load PCA scores and environmental data.
# 2. Calculate Pearson correlation coefficients between PC scores and environmental variables for each station.
# 3. Map these correlations to visualize the spatial distribution of relationships.
#
# ## Dependencies
# - pandas
# - geopandas
# - matplotlib
# - cartopy
# - scipy (for correlation)

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
from scipy.stats import pearsonr
import sys
from pathlib import Path
import shapely.wkb

# Add scripts to path
sys.path.append(str(Path.cwd().parents[1] / 'scripts'))
from paths import ProjectPaths

# Configure plots
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300


# Parameters
season = 'Summer'   
layer = 'bottom'
subset_dir = str(ProjectPaths.get_subset_dir(season, layer))  # default subset


# 1. Load Data
# Load PCA Scores
from pathlib import Path
subset_path = Path(subset_dir)
pca_scores_path = subset_path / 'pca_scores.csv'
pca_scores = pd.read_csv(pca_scores_path, index_col=0)

# Load Environmental Data (Cleaned)
env_data_path = ProjectPaths.PROCESSED_DATA_DIR / 'merged_gdf_saisuipoin_cleaned.feather'
env_data_df = pd.read_feather(env_data_path)

# Convert WKB to Geometry
try:
    if 'geometry' in env_data_df.columns:
        # Check first element to see if bytes
        if isinstance(env_data_df['geometry'].iloc[0], bytes):
             env_data_df['geometry'] = env_data_df['geometry'].apply(lambda x: shapely.wkb.loads(x))
    
    env_data = gpd.GeoDataFrame(env_data_df, geometry='geometry', crs="EPSG:4326")
    print("Loaded Env Data with Geometry.")
except Exception as e:
    print(f"Error converting geometry: {e}")
    if 'latitude' in env_data_df.columns and 'longitude' in env_data_df.columns:
        env_data = gpd.GeoDataFrame(
            env_data_df, 
            geometry=gpd.points_from_xy(env_data_df.longitude, env_data_df.latitude),
            crs="EPSG:4326"
        )
        print("Loaded Env Data with Lat/Lon fallback.")

# Only convert zettaicode to string for merging later.
if 'zettaicode' in env_data.columns:
    env_data['zettaicode'] = env_data['zettaicode'].astype(str)

# Ensure zettaicode is string for merging
pca_scores.index = pca_scores.index.astype(str)
env_data['zettaicode'] = env_data['zettaicode'].astype(str)

# Filter for Summer (June, July, August)
# Use surveymont directly to avoid date parse errors with invalid days
env_data['month'] = env_data['surveymont']
summer_data = env_data[env_data['month'].isin([6, 7, 8])].copy()

print("Data Loaded:")
print(f"PCA Scores: {pca_scores.shape}")
print(f"Environmental Data ({season} {layer}): {summer_data.shape}")


# 2. Prepare Environmental Variables per Station

# Ensure numeric types for aggregation
for col in ['temp', 'salt']:
    if col in summer_data.columns:
        summer_data[col] = pd.to_numeric(summer_data[col], errors='coerce')

surface_data = summer_data[summer_data['saisuipoin'] == 1]
bottom_data = summer_data[summer_data['saisuipoin'] == 2]

def get_station_time_series(df, var_col):
    # Pivot to get Year x Station matrix
    # Assuming one value per year (summer mean)
    # Use surveyyear if available
    if 'surveyyear' in df.columns:
        df['year'] = df['surveyyear']
    elif 'date' in df.columns:
        df['year'] = pd.to_datetime(df['date']).dt.year
        
    matrix = df.groupby(['year', 'zettaicode'])[var_col].mean().unstack()
    return matrix

# Extract matrices
sst_matrix = get_station_time_series(surface_data, 'temp')
sss_matrix = get_station_time_series(surface_data, 'salt')
sbt_matrix = get_station_time_series(bottom_data, 'temp')
sbs_matrix = get_station_time_series(bottom_data, 'salt')

print("PCA Scores Index (should be Years based on EOF logic):", pca_scores.index)


# 3. Calculate Correlations

def calculate_correlations(pc_scores, env_matrix, pc_col='PC1'):
    # pc_scores: Series (Year indexed)
    # env_matrix: DataFrame (Year x Station)
    
    correlations = {}
    p_values = {}

    # Ensure indices are integers for matching
    pc_scores.index = pc_scores.index.astype(int)
    env_matrix.index = env_matrix.index.astype(int)
    
    # Intersect years
    common_years = pc_scores.index.intersection(env_matrix.index)
    
    if len(common_years) < 5:
        print(f"Warning: Only {len(common_years)} common years for correlation.")
    
    for station in env_matrix.columns:
        # Get series
        s_env = env_matrix.loc[common_years, station]
        s_pc = pc_scores.loc[common_years]
        
        # Handle missing data
        valid = s_env.notna() & s_pc.notna()
        
        if valid.sum() > 5:
            corr, p = pearsonr(s_pc[valid], s_env[valid])
            correlations[station] = corr
            p_values[station] = p
        else:
            correlations[station] = np.nan
            p_values[station] = np.nan
            
    return pd.Series(correlations, name=f'{pc_col}_Corr'), pd.Series(p_values, name=f'{pc_col}_Pval')

# Initialize DataFrame to store station correlations
station_corrs = pd.DataFrame(index=sst_matrix.columns)
station_corrs.index.name = 'zettaicode'

# Calculate for PC1 and PC2 vs All 4 Env Vars
for pc in ['PC1', 'PC2']:
    if pc in pca_scores.columns:
        # SST
        r, p = calculate_correlations(pca_scores[pc], sst_matrix, pc)
        station_corrs[f'{pc}_SST_Corr'] = r
        
        # SSS
        r, p = calculate_correlations(pca_scores[pc], sss_matrix, pc)
        station_corrs[f'{pc}_SSS_Corr'] = r
        
        # SBT
        r, p = calculate_correlations(pca_scores[pc], sbt_matrix, pc)
        station_corrs[f'{pc}_SBT_Corr'] = r
        
        # SBS
        r, p = calculate_correlations(pca_scores[pc], sbs_matrix, pc)
        station_corrs[f'{pc}_SBS_Corr'] = r

# Merge with Geometry
gdf_stations = env_data.drop_duplicates(subset='zettaicode')[['zettaicode', 'geometry']].set_index('zettaicode')
corr_map_data = gdf_stations.join(station_corrs, how='inner')

print("Correlation Matrix Head:")
print(corr_map_data.head())


# 4. Visualization (User Style)

def plot_correlation_maps(gdf, variable_type, title_prefix):
    # variable_type: 'SST', 'SSS', 'SBT', 'SBS'
    
    fig, axes = plt.subplots(2, 1, figsize=(10, 12), subplot_kw={'projection': ccrs.PlateCarree()})
    
    fig.suptitle(f'Correlation between PCs and {title_prefix}', fontsize=16, fontweight='bold', y=0.95)

    components = [
        (f'PC1_{variable_type}_Corr', 'PC1'), 
        (f'PC2_{variable_type}_Corr', 'PC2')
    ]

    for ax, (col, pc_name) in zip(axes, components):
        if col not in gdf.columns:
            continue
            
        pad = 0.1
        min_lon, min_lat, max_lon, max_lat = gdf.total_bounds
        ax.set_extent([min_lon - pad, max_lon + pad, min_lat - pad, max_lat + pad], crs=ccrs.PlateCarree())

        ax.add_feature(cfeature.LAND, facecolor='whitesmoke', edgecolor='gray')
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
        ax.gridlines(draw_labels=True, linestyle='--', alpha=0.4, linewidth=0.5)

        # Scatter plot
        # Using correlation range -1 to 1
        sc = ax.scatter(
            gdf.geometry.x,
            gdf.geometry.y,
            c=gdf[col],
            s=gdf[col].abs() * 300,  # Scaled by correlation magnitude
            cmap='PRGn',
            edgecolor='k',
            linewidth=0.5,
            alpha=0.85,
            transform=ccrs.PlateCarree(),
            vmin=-1, vmax=1  # Correlation bounds
        )
        ax.set_title(f'{pc_name} vs {variable_type} Correlation', fontsize=12, fontweight='bold')

    # Reduce vertical spacing
    plt.subplots_adjust(hspace=0.08, top=0.92)

    # Colorbar
    cbar = fig.colorbar(sc, ax=axes.ravel().tolist(), orientation='vertical', fraction=0.04, pad=0.1)
    cbar.set_label('Pearson Correlation (Red=Positive, Blue=Negative)')

    save_path = ProjectPaths.FIGURES_DIR / f'pca_corr_{variable_type}.png'
    plt.savefig(save_path, bbox_inches='tight')
    print(f"Saved plot to {save_path}")
    plt.show()

# Generate plots for all 4 variables
if not corr_map_data.empty:
    plot_correlation_maps(corr_map_data, 'SST', 'Sea Surface Temperature')
    plot_correlation_maps(corr_map_data, 'SSS', 'Sea Surface Salinity')
    plot_correlation_maps(corr_map_data, 'SBT', 'Sea Bottom Temperature')
    plot_correlation_maps(corr_map_data, 'SBS', 'Sea Bottom Salinity')
else:
    print("No correlation map data to plot.")



def plot_pc_correlations(gdf, pc_name):
    # pc_name: 'PC1' or 'PC2'
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12), subplot_kw={'projection': ccrs.PlateCarree()})
    fig.suptitle(f'{pc_name} Correlations with Environmental Factors', fontsize=18, fontweight='bold', y=0.95)

    params = [
        ('SST', f'{pc_name}_SST_Corr', 'Sea Surface Temp'),
        ('SSS', f'{pc_name}_SSS_Corr', 'Sea Surface Salinity'),
        ('SBT', f'{pc_name}_SBT_Corr', 'Sea Bottom Temp'),
        ('SBS', f'{pc_name}_SBS_Corr', 'Sea Bottom Salinity')
    ]

    for ax, (var_name, col, title) in zip(axes.ravel(), params):
        if col not in gdf.columns:
            ax.text(0.5, 0.5, "Data Missing", transform=ax.transAxes, ha='center')
            continue
            
        pad = 0.1
        min_lon, min_lat, max_lon, max_lat = gdf.total_bounds
        ax.set_extent([min_lon - pad, max_lon + pad, min_lat - pad, max_lat + pad], crs=ccrs.PlateCarree())

        ax.add_feature(cfeature.LAND, facecolor='whitesmoke', edgecolor='gray')
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
        ax.gridlines(draw_labels=True, linestyle='--', alpha=0.4, linewidth=0.5)

        # Scatter plot
        sc = ax.scatter(
            gdf.geometry.x,
            gdf.geometry.y,
            c=gdf[col],
            s=gdf[col].abs() * 300,
            cmap='PRGn',
            edgecolor='k',
            linewidth=0.5,
            alpha=0.9,
            transform=ccrs.PlateCarree(),
            vmin=-1, vmax=1
        )
        ax.set_title(title, fontsize=12, fontweight='bold')

    plt.subplots_adjust(hspace=0.2, wspace=0.1, top=0.90)

    # Global Colorbar
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    cbar = fig.colorbar(sc, cax=cbar_ax, orientation='vertical')
    cbar.set_label('Pearson Correlation (Red=Positive, Blue=Negative)', fontsize=12)

    save_path = ProjectPaths.FIGURES_DIR / f'pca_{pc_name}_env_corr_grid.png'
    plt.savefig(save_path, bbox_inches='tight')
    print(f"Saved plot to {save_path}")
    plt.show()

# Generate for PC1 and PC2
print("Generating Grid Plots...")
if not corr_map_data.empty:
    plot_pc_correlations(corr_map_data, 'PC1')
    plot_pc_correlations(corr_map_data, 'PC2')


# --- PARAMETERS ---
rank_metric = 'PC1_SBT_Corr'  # Correlation metric to rank by
top_n = 10                    # Number of stations to include
corr_cutoff = 0.0             # Minimum absolute correlation value

# --- SELECTION LOGIC ---
# Create a temporary column for absolute correlation to rank by magnitude
station_corrs['abs_rank'] = station_corrs[rank_metric].abs()

# Sort by absolute correlation in descending order
ranked_stations = station_corrs.sort_values(by='abs_rank', ascending=False)

# Filter by cutoff
filtered_stations = ranked_stations[ranked_stations['abs_rank'] >= corr_cutoff]

# Select top N zettaicodes
selected_zettaicodes = filtered_stations.head(top_n).index.tolist()

print(f"Selecting top {top_n} strongest correlated stations (Abs({rank_metric}) >= {corr_cutoff})")
print(f"Found {len(selected_zettaicodes)} stations:")
print(selected_zettaicodes)


import matplotlib.cm as cm

# --- DATA PREPARATION ---
target_y_col = 'do_'

# Ensure DO column is numeric and get data matrix
if target_y_col in bottom_data.columns:
    bottom_data[target_y_col] = pd.to_numeric(bottom_data[target_y_col], errors='coerce')
    do_matrix = get_station_time_series(bottom_data, target_y_col)
else:
    print(f"Error: Column '{target_y_col}' not found.")
    do_matrix = pd.DataFrame()

# --- WATER MASS (DIVISION) PREPARATION ---
# Create mapping: Station -> Division
div_col = 'division' 
if div_col in summer_data.columns:
    station_divisions = summer_data[['zettaicode', div_col]].drop_duplicates().set_index('zettaicode')[div_col]
else:
    print(f"Warning: '{div_col}' column not found. Using default color.")
    station_divisions = pd.Series('Unknown', index=selected_zettaicodes)

# Generate colors for divisions
unique_divisions = station_divisions.loc[station_divisions.index.intersection(selected_zettaicodes)].unique()
# Use a high-contrast colormap (e.g., tab10 or Set1)
colors = plt.cm.tab10(np.linspace(0, 1, len(unique_divisions)))
div_color_map = dict(zip(unique_divisions, colors))

# --- PLOTTING ---
fig, ax = plt.subplots(figsize=(12, 8))

# Track which divisions we've added to the legend
plotted_divisions = set()

for station_id in selected_zettaicodes:
    if station_id in sbt_matrix.columns and station_id in do_matrix.columns:
        x_vals = sbt_matrix[station_id]
        y_vals = do_matrix[station_id]
        
        # Get Division and Color
        div = station_divisions.get(station_id, 'Unknown')
        color = div_color_map.get(div, 'gray')
        
        # Label only new divisions for the legend
        label = div if div not in plotted_divisions else None
        
        # Plot Scatter
        ax.scatter(x_vals, y_vals, c=[color], label=label, alpha=0.7, edgecolors='white', s=60)
        plotted_divisions.add(div)
        
        # Annotate Station ID (at the mean center of the station's points)
        # We add the correlation value to the label for context
        r_val = station_corrs.loc[station_id, rank_metric]
        ax.annotate(f"{station_id}", 
                    (x_vals.mean(), y_vals.mean()),
                    fontsize=9, weight='bold', ha='center', va='center',
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.6))

# Formatting
ax.set_xlabel('Sea Bottom Temperature (°C)')
ax.set_ylabel('Dissolved Oxygen (DO)')
ax.set_title(f'SBT vs DO: Top {top_n} Strongest Correlations ({rank_metric})')
ax.grid(True, linestyle='--', alpha=0.5)

# Legend for Water Mass (Division)
ax.legend(title="Water Mass (Division)", bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0.)

plt.tight_layout()
plt.show()



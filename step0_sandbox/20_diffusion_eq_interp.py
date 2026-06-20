import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from shapely.geometry import Point
import scipy.ndimage as ndimage
import scipy.interpolate as interp
import sys
import os
from pathlib import Path

# Ensure local scripts are importable
project_root = Path("..").resolve()
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths

# Configure logging to see updates
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("Project paths initialized.")

# Load data
subset_path = ProjectPaths.get_subset_dir('Summer', 'bottom')
yearly_do_df = pd.read_csv(subset_path / "yearly_do_df.csv", index_col=0)
yearly_do_df.index = yearly_do_df.index.astype(str).str.zfill(8)

merged_gdf = gpd.read_feather(ProjectPaths.MERGED_DATA_FILE)
station_locs = merged_gdf.drop_duplicates('zettaicode').set_index('zettaicode')
station_locs = station_locs.loc[yearly_do_df.index]

print(f"Loaded {len(yearly_do_df)} observations and {len(station_locs)} station coordinates.")
yearly_do_df.head()

# 1. Load Custom Boundary Shapefile (WGS84)
sis_boundary = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp")

# 2. Project to UTM Zone 53N for meters
utm_crs = 'EPSG:32653'
sis_boundary_utm = sis_boundary.to_crs(utm_crs)
bounds_utm = sis_boundary_utm.total_bounds

# 3. Create grid (e.g., 2000m resolution)
GRID_RES = 2000
grid_x_1d = np.arange(bounds_utm[0], bounds_utm[2], GRID_RES)
grid_y_1d = np.arange(bounds_utm[1], bounds_utm[3], GRID_RES)
grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)

# Flatten for point-in-polygon check
pts = gpd.GeoSeries([Point(x, y) for x, y in zip(grid_x.flatten(), grid_y.flatten())], crs=utm_crs)
points_gdf = gpd.GeoDataFrame(geometry=pts)

# Filter points within the water boundary
water_points = gpd.sjoin(points_gdf, sis_boundary_utm, predicate='within')

# Create a 2D boolean mask for water (True = Water, False = Land/Outside)
water_mask = np.zeros(grid_x.shape, dtype=bool)
valid_indices = water_points.index.values
water_mask.flat[valid_indices] = True

# Also extract valid water coordinates for unstructured usage (like Kriging or evaluation)
water_grid_x = grid_x.flatten()[valid_indices]
water_grid_y = grid_y.flatten()[valid_indices]

print(f"Grid dimensions: {grid_x.shape}")
print(f"Total grid points: {grid_x.size}, Water points: {len(water_points)}")

def run_diffusion_interpolation(year_data, station_locs_gdf, grid_x_1d, grid_y_1d, water_mask, max_iters=2000, tol=1e-4, omega=1.7):
    """
    Runs Red-Black SOR to solve the diffusion equation on the grid.
    """
    # Initialize the solution grid with NaNs (Land will remain NaN)
    Z = np.full(water_mask.shape, np.nan)
    
    # Provide an initial guess for water cells (e.g., mean observed DO)
    mean_val = year_data['DO_mgL'].mean()
    Z[water_mask] = mean_val
    
    # Create mask to track fixed observation cells
    fixed_mask = np.zeros_like(water_mask, dtype=bool)
    
    # Map observations to the nearest grid cell
    for idx, row in year_data.iterrows():
        station_id = row['Station_ID']
        if station_id in station_locs_gdf.index:
            pt = station_locs_gdf.loc[station_id].geometry
            # Find closest grid indices
            ix = np.argmin(np.abs(grid_x_1d - pt.x))
            iy = np.argmin(np.abs(grid_y_1d - pt.y))
            
            # Snap to grid if it's considered water
            if water_mask[iy, ix]:
                Z[iy, ix] = row['DO_mgL']
                fixed_mask[iy, ix] = True
            else:
                # If observation slightly in land due to grid resolution, find nearest water cell
                dist = (grid_x - pt.x)**2 + (grid_y - pt.y)**2
                dist[~water_mask] = np.inf
                nearest_water_flat_idx = np.argmin(dist)
                iy_nearest, ix_nearest = np.unravel_index(nearest_water_flat_idx, water_mask.shape)
                Z[iy_nearest, ix_nearest] = row['DO_mgL']
                fixed_mask[iy_nearest, ix_nearest] = True

    # Red-Black masks
    # Create checkerboard pattern
    i_indices, j_indices = np.indices(Z.shape)
    red_mask = (i_indices + j_indices) % 2 == 0
    black_mask = ~red_mask

    # Convolution kernel for 4-neighbors (Laplacian)
    kernel = np.array([[0, 1, 0], 
                       [1, 0, 1], 
                       [0, 1, 0]])
                       
    # Pre-calculate neighbor counts for water cells (handling Neumann BC automatically)
    # A cell near land will have < 4 valid neighbors to average over
    water_float = water_mask.astype(float)
    W = ndimage.convolve(water_float, kernel, mode='constant', cval=0.0)
    
    def update(Z_current, mask):
        # Only convolve over water cells (treat land and NaNs as 0 flux)
        Z_water = np.nan_to_num(Z_current, copy=True, nan=0.0) * water_mask
        
        # Sum of neighbors
        Z_sum = ndimage.convolve(Z_water, kernel, mode='constant', cval=0.0)
        
        # Average of neighbors (avoid div by zero, which shouldn't happen for water cells except 0-neighbor isolated grids)
        with np.errstate(divide='ignore', invalid='ignore'):
            Z_new = np.where(W > 0, Z_sum / W, Z_current)
            
        # Update only cells that are in the current color, are water, and are NOT fixed observations
        update_mask = mask & water_mask & (~fixed_mask)
        Z_current[update_mask] = (1 - omega) * Z_current[update_mask] + omega * Z_new[update_mask]
        return Z_current

    # SOR Iteration Loop
    for it in range(max_iters):
        Z_old = Z.copy()
        
        # Update Red cells, then Black cells
        Z = update(Z, red_mask)
        Z = update(Z, black_mask)
        
        # Check convergence
        diff = np.abs(Z[water_mask] - Z_old[water_mask])
        max_diff = np.nanmax(diff) if len(diff) > 0 else 0
        
        if (it + 1) % 200 == 0:
            logging.info(f"Iteration {it+1}: max diff = {max_diff:.6f}")
            
        if max_diff < tol:
            logging.info(f"Converged after {it+1} iterations! Max diff: {max_diff:.6f}")
            break
            
    if it == max_iters - 1:
        logging.warning("Reached max iterations without full convergence.")
        
    return Z

# Prepare specific year data
target_year = '1991'
year_data = yearly_do_df[target_year].dropna().reset_index()
year_data.columns = ['Station_ID', 'DO_mgL']

# WGS is already in station_locs for WGS coordinates
if station_locs.crs != 'EPSG:4326':
    station_locs_wgs = station_locs.to_crs('EPSG:4326')
else:
    station_locs_wgs = station_locs.copy()
    
station_locs_utm = station_locs_wgs.to_crs(utm_crs)

print(f"Running Diffusion Interpolation for {target_year}...")
Z_diff = run_diffusion_interpolation(year_data, station_locs_utm, grid_x_1d, grid_y_1d, water_mask)


# Helper: convert UTM grid back to WGS84 for Cartopy plotting
grid_gdf = gpd.GeoDataFrame(
    {'z_pred': Z_diff[water_mask]},
    geometry=[Point(x, y) for x, y in zip(water_grid_x, water_grid_y)],
    crs='EPSG:32653'
).to_crs(epsg=4326)

# We need a 2D grid for plotting
lon_wgs = np.full(grid_x.shape, np.nan)
lat_wgs = np.full(grid_y.shape, np.nan)

lon_wgs[water_mask] = grid_gdf.geometry.x.values
lat_wgs[water_mask] = grid_gdf.geometry.y.values

# Make sure station_locs_wgs is correctly extracted for mapping
valid_stations = year_data['Station_ID'].unique()
valid_locs_wgs = station_locs_wgs.loc[valid_stations]

fig, ax = plt.subplots(figsize=(12, 8), subplot_kw={'projection': ccrs.PlateCarree()})

# Base map features
ax.add_feature(cfeature.LAND, facecolor='lightgray')
ax.add_feature(cfeature.COASTLINE, linewidth=0.5)

# Plot sis boundary custom
sis_boundary_wgs = sis_boundary.to_crs('EPSG:4326')
sis_boundary_wgs.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=1)

# Plot the predicted surface using pcolormesh on the grid
# Since our coordinates are on a uniform UTM grid but not uniform in WGS84, scatter is safer for perfect alignment, or we can use pcolormesh and transform.
# Given it's a dense grid, scatter works well and maps perfectly to the water_mask.
scatter_pred = ax.scatter(
    lon_wgs[water_mask], lat_wgs[water_mask],
    c=Z_diff[water_mask],
    cmap='viridis',
    s=15, # Adjust size
    marker='s', # Use square to look like grid cells
    alpha=0.9,
    edgecolor='none'
)

# Plot actual observations
ax.scatter(valid_locs_wgs.geometry.x, valid_locs_wgs.geometry.y, color='red', marker='^', s=40, edgecolor='black', linewidth=0.5, label='Observations', zorder=5)

cbar = plt.colorbar(scatter_pred, ax=ax, orientation='vertical', shrink=0.7, pad=0.02)
cbar.set_label('DO Concentration (mg/L)', fontsize=12)

ax.set_title(f"Diffusion Equation Interpolation: Summer DO ({target_year})", fontsize=15)
ax.set_extent([130.8, 135.3, 33.1, 34.9], crs=ccrs.PlateCarree())

gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.5)
gl.top_labels = False
gl.right_labels = False

plt.legend(loc='lower right')
plt.tight_layout()
plt.show()

# 1. Perform standard Griddata Linear Interpolation
obs_coords = np.column_stack([valid_locs_wgs.to_crs(utm_crs).geometry.x, valid_locs_wgs.to_crs(utm_crs).geometry.y])
obs_vals = year_data['DO_mgL'].values

Z_linear = interp.griddata(obs_coords, obs_vals, (grid_x, grid_y), method='linear')

# Plot comparison
fig, axes = plt.subplots(1, 2, figsize=(20, 8), subplot_kw={'projection': ccrs.PlateCarree()})
ax1, ax2 = axes

# Setup both axes
for ax in axes:
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    sis_boundary_wgs.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=1)
    ax.set_extent([130.8, 135.3, 33.1, 34.9], crs=ccrs.PlateCarree())
    ax.scatter(valid_locs_wgs.geometry.x, valid_locs_wgs.geometry.y, color='red', marker='^', s=20, edgecolor='black', zorder=5)

# Ax1: Linear Interpolation
sc1 = ax1.scatter(lon_wgs[water_mask], lat_wgs[water_mask], c=Z_linear[water_mask], cmap='viridis', s=10, marker='s')
ax1.set_title('Standard Linear Interpolation', fontsize=14)

# Ax2: Diffusion
sc2 = ax2.scatter(lon_wgs[water_mask], lat_wgs[water_mask], c=Z_diff[water_mask], cmap='viridis', s=10, marker='s')
ax2.set_title('Diffusion Interpolation', fontsize=14)

plt.colorbar(sc2, ax=axes, orientation='horizontal', shrink=0.5, pad=0.05, label='DO (mg/L)')
plt.show()

validation_years = list(yearly_do_df.columns[:5])

loocv_results = []
logging.getLogger().setLevel(logging.WARNING) # Suppress iteration logs for LOOCV

print("Starting LOOCV for the first 5 years...")
for year in validation_years:
    year_data_full = yearly_do_df[year].dropna().reset_index()
    year_data_full.columns = ['Station_ID', 'DO_mgL']
    valid_stations_yr = year_data_full['Station_ID'].unique()
    
    print(f"Processing {year} ({len(valid_stations_yr)} stations)...")
    
    for i, hold_out_station in enumerate(valid_stations_yr):
        # 1. Split data
        train_data = year_data_full[year_data_full['Station_ID'] != hold_out_station]
        test_obs = year_data_full[year_data_full['Station_ID'] == hold_out_station].iloc[0]
        
        # 2. Re-run diffusion model (using looser tolerance / fewer iterations to speed up LOOCV)
        Z_cv = run_diffusion_interpolation(train_data, station_locs_utm, grid_x_1d, grid_y_1d, water_mask, max_iters=1000, tol=1e-3)
        
        # 3. Predict at hold-out location
        pt = station_locs_utm.loc[hold_out_station].geometry
        ix = np.argmin(np.abs(grid_x_1d - pt.x))
        iy = np.argmin(np.abs(grid_y_1d - pt.y))
        
        if water_mask[iy, ix]:
            predicted_do = Z_cv[iy, ix]
        else:
            # Nearest water point
            dist = (grid_x - pt.x)**2 + (grid_y - pt.y)**2
            dist[~water_mask] = np.inf
            nearest = np.argmin(dist)
            iy_n, ix_n = np.unravel_index(nearest, water_mask.shape)
            predicted_do = Z_cv[iy_n, ix_n]
            
        actual_do = test_obs['DO_mgL']
        
        loocv_results.append({
            'Year': year,
            'Station_ID': hold_out_station,
            'Actual_DO': actual_do,
            'Predicted_DO': predicted_do,
            'Error': predicted_do - actual_do
        })

loocv_df = pd.DataFrame(loocv_results)
loocv_df.dropna(subset=['Predicted_DO'], inplace=True) # removing any NaNs if occurred
print("
LOOCV complete.")

from sklearn.metrics import mean_absolute_error, mean_squared_error

mae = mean_absolute_error(loocv_df['Actual_DO'], loocv_df['Predicted_DO'])
rmse = np.sqrt(mean_squared_error(loocv_df['Actual_DO'], loocv_df['Predicted_DO']))

print(f"Diffusion Interpolation LOOCV Performance (First 5 Years):")
print(f"MAE:  {mae:.3f} mg/L")
print(f"RMSE: {rmse:.3f} mg/L")

fig, ax = plt.subplots(figsize=(7, 6))

ax.scatter(loocv_df['Actual_DO'], loocv_df['Predicted_DO'], alpha=0.6, edgecolors='k')
ax.plot([0, 10], [0, 10], 'r--', label='1:1 Line')

ax.set_xlabel('Actual Summer Bottom DO (mg/L)')
ax.set_ylabel('Predicted Summer Bottom DO (mg/L)')
ax.set_title(f'Diffusion LOOCV (MAE: {mae:.2f} | RMSE: {rmse:.2f})')
ax.set_xlim(2, 9)
ax.set_ylim(2, 9)
ax.grid(alpha=0.3)
ax.legend()

plt.tight_layout()
plt.show()

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import math
from pathlib import Path
from scipy.interpolate import griddata
import sys

# Setup paths
CURRENT_SCRIPT = Path(__file__).resolve()
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

project_root = CURRENT_SCRIPT.parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
style_path = ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'
if style_path.exists():
    plt.style.use(str(style_path))

# Target stations (Ise-Mikawa Bay transect)
TARGET_STATIONS = ['00002355', '00002360', '00002359', '00002331', '00002337', '00002343']

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def create_test_plot():
    print("Loading merged data...")
    df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    
    df['zettaicode'] = df['zettaicode'].astype(str).str.zfill(8)
    df = df[df['zettaicode'].isin(TARGET_STATIONS)].copy()
    
    print(f"Data shape after filtering stations: {df.shape}")
    if df.empty:
        print("No data found for target stations.")
        return
        
    # Get station coordinates and max depths (assuming coordinates don't change much, take mean)
    station_info = {}
    for st in TARGET_STATIONS:
        st_data = df[df['zettaicode'] == st]
        if not st_data.empty:
            lat = pd.to_numeric(st_data['latitude'], errors='coerce').mean()
            lon = pd.to_numeric(st_data['longitude'], errors='coerce').mean()
            depth = pd.to_numeric(st_data['depth'], errors='coerce').max()
            station_info[st] = {'lat': lat, 'lon': lon, 'depth': depth}
            
    # Calculate cumulative distance
    cumulative_dist = 0.0
    for i, st in enumerate(TARGET_STATIONS):
        if i == 0:
            station_info[st]['dist'] = 0.0
        else:
            prev_st = TARGET_STATIONS[i-1]
            dist = haversine(station_info[prev_st]['lat'], station_info[prev_st]['lon'], 
                             station_info[st]['lat'], station_info[st]['lon'])
            cumulative_dist += dist
            station_info[st]['dist'] = cumulative_dist
            
    # Test setting
    test_year = 1999
    test_season = 'Summer'
    test_param = 'wtemp'
    
    print(f"Filtering for Year: {test_year}, Season: {test_season}")
    subset = df[(df['surveyyear'] == test_year) & (df['season'] == test_season)].copy()
    subset = subset[subset['saisuipoin'].isin([1, 2])]
    
    subset['saisuidept'] = pd.to_numeric(subset['saisuidept'], errors='coerce')
    subset['wtemp'] = pd.to_numeric(subset['wtemp'], errors='coerce')
    subset = subset.dropna(subset=['saisuidept', 'wtemp', 'zettaicode'])
    
    subset['distance'] = subset['zettaicode'].map(lambda x: station_info[x]['dist'])
    
    if subset.empty:
        print("No valid data points for the test parameters.")
        return
        
    # Data for interpolation
    x = subset['distance'].values
    y = subset['saisuidept'].values
    z = subset['wtemp'].values
    
    max_dist = station_info[TARGET_STATIONS[-1]]['dist']
    max_depth_all = max([info['depth'] for info in station_info.values() if pd.notna(info['depth'])])
    
    grid_x, grid_y = np.mgrid[0:max_dist:100j, 0:max_depth_all:100j]
    
    try:
        grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
    except Exception as e:
        print(f"Interpolation failed: {e}")
        return
        
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 1. Filled contour plot (warm colormap)
    contour = ax.contourf(grid_x, grid_y, grid_z, levels=20, cmap='YlOrRd', extend='both')
    
    # 2. Add contour lines and labels
    contour_lines = ax.contour(grid_x, grid_y, grid_z, levels=10, colors='k', linewidths=0.5)
    ax.clabel(contour_lines, inline=True, fontsize=10, fmt='%.1f')
    
    cbar = fig.colorbar(contour, ax=ax)
    cbar.set_label('Water Temperature (°C)', rotation=270, labelpad=15)
    
    # 3. Draw Bathymetry (Seabed) as grey polygon
    dists = [station_info[st]['dist'] for st in TARGET_STATIONS]
    depths = [station_info[st]['depth'] for st in TARGET_STATIONS]
    # Fill from seabed to bottom of axis
    ax.fill_between(dists, depths, max_depth_all + 5, color='gray')
    
    # Plot original points to see sampling locations (black filled dots)
    ax.scatter(x, y, color='black', s=30)
    
    ax.set_ylim(max_depth_all + 5, 0)
    ax.set_xlim(0, max_dist)
    
    # Label top x-axis with station names if desired, or keep distance
    ax.set_xlabel('Distance from shore (km)')
    ax.set_ylabel('Depth (m)')
    ax.set_title(f'Cross-section: Water Temperature\n{test_season} {test_year}')
    
    # Add station markers on top axis
    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    ax2.set_xticks(dists)
    ax2.set_xticklabels(TARGET_STATIONS, rotation=45)
    ax2.set_xlabel('Station')
    
    plt.tight_layout()
    out_path = OUTPUT_DIR / f'test_cross_section_{test_param}_{test_year}_{test_season}.png'
    plt.savefig(out_path, dpi=300)
    plt.close()
    
    print(f"Test plot saved to: {out_path}")

if __name__ == "__main__":
    create_test_plot()

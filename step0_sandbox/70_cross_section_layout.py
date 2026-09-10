import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import math
from pathlib import Path
from scipy.interpolate import griddata
import sys
import gsw
import warnings

# Suppress warnings for all-NaN slices
warnings.filterwarnings('ignore', category=RuntimeWarning)

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
from utils.mapping_config import MappingConfig
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

def get_param_config(param, df):
    var_map = {
        'wtemp': 'wtemp',
        'salinity': 'salt2' if 'salt2' in df.columns else 'salt',
        'DO': 'do_',
        'density': 'density',
        'DOC': 'doc2' if 'doc2' in df.columns else 'doc'
    }
    col = var_map[param]
    cfg = MappingConfig.get_var_settings(col)
    
    return {
        'col': col,
        'cmap': cfg['cmap'],
        'vmin': cfg['vmin'],
        'vmax': cfg['vmax'],
        'label': cfg['label'],
        'extend': cfg.get('extend', 'both')
    }

def main():
    print("Loading merged data...")
    df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    
    # Pre-compute density if needed
    if 'density' not in df.columns:
        salt_col = 'salt2' if 'salt2' in df.columns else 'salt'
        df['salt_calc'] = pd.to_numeric(df[salt_col], errors='coerce')
        df['wtemp_calc'] = pd.to_numeric(df['wtemp'], errors='coerce')
        df['density'] = gsw.rho(df['salt_calc'], df['wtemp_calc'], 0) - 1000
    
    df['zettaicode'] = df['zettaicode'].astype(str).str.zfill(8)
    df = df[df['zettaicode'].isin(TARGET_STATIONS)].copy()
    
    if df.empty:
        print("No data found for target stations.")
        return
        
    # Get station coordinates and max depths
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
            
    years = [1999, 2008]
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    parameters = ['wtemp', 'salinity', 'DO', 'density', 'DOC']
    
    max_dist = station_info[TARGET_STATIONS[-1]]['dist']
    max_depth_all = max([info['depth'] for info in station_info.values() if pd.notna(info['depth'])])
    
    dists = [station_info[st]['dist'] for st in TARGET_STATIONS]
    depths = [station_info[st]['depth'] for st in TARGET_STATIONS]
    
    generated_count = 0
    for year in years:
        for season in seasons:
            for param in parameters:
                config = get_param_config(param, df)
                col = config['col']
                
                subset = df[(df['surveyyear'] == year) & (df['season'] == season)].copy()
                subset = subset[subset['saisuipoin'].isin([1, 2])]
                
                if col not in subset.columns:
                    continue
                    
                subset['saisuidept'] = pd.to_numeric(subset['saisuidept'], errors='coerce')
                subset[col] = pd.to_numeric(subset[col], errors='coerce')
                subset = subset.dropna(subset=['saisuidept', col, 'zettaicode'])
                
                if subset.empty or len(subset) < 3: # Need minimum points for interpolation
                    print(f"Skipping {param} {year} {season} (not enough data)")
                    continue
                    
                subset['distance'] = subset['zettaicode'].map(lambda x: station_info[x]['dist'])
                
                x = subset['distance'].values
                y = subset['saisuidept'].values
                z = subset[col].values
                
                grid_x, grid_y = np.mgrid[0:max_dist:100j, 0:max_depth_all:100j]
                
                try:
                    grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
                except Exception as e:
                    print(f"Interpolation failed for {param} {year} {season}: {e}")
                    continue
                    
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # Check if all grid_z is nan
                if np.isnan(grid_z).all():
                    print(f"Skipping {param} {year} {season} (interpolation produced all NaNs)")
                    plt.close(fig)
                    continue
                    
                # 1. Filled contour plot
                try:
                    levels = np.linspace(config['vmin'], config['vmax'], 21)
                    line_levels = np.linspace(config['vmin'], config['vmax'], 11)
                    contour = ax.contourf(grid_x, grid_y, grid_z, levels=levels, 
                                          cmap=config['cmap'], extend=config['extend'])
                    # 2. Add contour lines and labels
                    contour_lines = ax.contour(grid_x, grid_y, grid_z, levels=line_levels, colors='k', linewidths=0.5)
                    ax.clabel(contour_lines, inline=True, fontsize=10, fmt='%.1f')
                except ValueError as e:
                    print(f"Skipping {param} {year} {season} (contour failed: {e})")
                    plt.close(fig)
                    continue
                
                # Colorbar
                cbar = fig.colorbar(contour, ax=ax)
                cbar.set_label(config['label'], rotation=270, labelpad=15)
                
                # 3. Draw Bathymetry (Seabed) as grey polygon
                ax.fill_between(dists, depths, max_depth_all + 5, color='gray')
                
                # 4. Plot original points as black dots
                ax.scatter(x, y, color='black', s=30)
                
                ax.set_ylim(max_depth_all + 5, 0)
                ax.set_xlim(0, max_dist)
                
                ax.set_xlabel('Distance from shore (km)')
                ax.set_ylabel('Depth (m)')
                ax.set_title(f'Cross-section: {param}\n{season} {year}')
                
                # Add station markers on top axis
                ax2 = ax.twiny()
                ax2.set_xlim(ax.get_xlim())
                ax2.set_xticks(dists)
                ax2.set_xticklabels(TARGET_STATIONS, rotation=45)
                ax2.set_xlabel('Station')
                
                plt.tight_layout()
                out_path = OUTPUT_DIR / f'cross_section_{param}_{year}_{season}.png'
                
                # Try saving, catch any OSError file lock issues
                try:
                    plt.savefig(out_path, dpi=300)
                    generated_count += 1
                except OSError as e:
                    print(f"Could not save {out_path.name} (File might be locked by another program). Error: {e}")
                
                plt.close(fig)
                
    print(f"\nSuccessfully generated {generated_count} cross-section figures in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()

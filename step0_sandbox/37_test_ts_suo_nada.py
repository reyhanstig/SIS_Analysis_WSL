import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import math
from pathlib import Path
import matplotlib.lines as mlines
import matplotlib.cm as cm

# Add project root to sys.path to import scripts.paths
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from scripts.paths import ProjectPaths

# Apply the global project style
plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))

def get_time_series_matrix(df, param, season_filter, saisuipoin=None):
    mask = df['season'] == season_filter
    if saisuipoin is not None:
        mask &= df['saisuipoin'] == saisuipoin
    subset = df.loc[mask, ['surveyyear', 'zettaicode', param]].copy()
    subset[param] = pd.to_numeric(subset[param], errors='coerce')
    matrix = subset.groupby(['surveyyear', 'zettaicode'])[param].mean().unstack()
    matrix.index = matrix.index.astype(int)
    return matrix

def main():
    # Parameters matching the original test script
    pc_name = "PC1"
    parameter = "Spring_1_CHLA"
    season = "Spring"
    saisuipoin = 1
    raw_param = "chlorophyl"
    target_division = "Suo Nada"
    
    print("Loading data...")
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    # Filter to Seto Inland Sea only and remove unassigned divisions
    merged_df = merged_df[merged_df['watermass_name'] == 'Seto Inland Sea']
    merged_df = merged_df[merged_df['division'] != '—']
    
    # Load correlation data
    subset_dir = ProjectPaths.get_subset_dir('Summer', 'bottom')
    corr_path = subset_dir / f'pca_env_corr_{pc_name.lower()}.csv'
    if not corr_path.exists():
        corr_path = subset_dir / f'pca_nutr_corr_{pc_name.lower()}.csv'
    
    corr_df = pd.read_csv(corr_path, index_col=0)
    corr_df.index = corr_df.index.astype(str).str.zfill(8)
    
    # Filter significant stations
    p_col = parameter + '_pval'
    # Drop rows where p-value is NaN
    corr_df = corr_df.dropna(subset=[p_col])
    sig_stations = corr_df[corr_df[p_col] <= 0.05]
    
    if sig_stations.empty:
        print(f"No significant stations found for {parameter}.")
        return
        
    # Get station regions
    station_regions = merged_df[['zettaicode', 'division']].drop_duplicates().set_index('zettaicode')['division']
    
    # Map significant stations to their regions and filter for Suo Nada only
    sig_station_regions = station_regions[station_regions.index.isin(sig_stations.index)].dropna()
    suo_nada_stns = sig_station_regions[sig_station_regions == target_division].index
    
    if len(suo_nada_stns) == 0:
        print(f"No significant stations found in {target_division} for {parameter}.")
        return
        
    print(f"Found {len(suo_nada_stns)} significant stations in {target_division}:")
    for stn in suo_nada_stns:
        print(f"  Station: {stn}, p-value: {sig_stations.loc[stn, p_col]:.6f}")
        
    # Get time series matrix
    print(f"Building time series matrix for {parameter}...")
    ts_matrix = get_time_series_matrix(merged_df, raw_param, season, saisuipoin)
    
    # Single plot setup
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Use tab10 orange color for Suo Nada (which matches cmap(1) from the original script)
    # Using matplotlib.colormaps.get_cmap to avoid deprecation warnings
    cmap = plt.colormaps.get_cmap('tab10')
    base_color = cmap(1)  # Suo Nada orange color
    
    for stn in suo_nada_stns:
        if stn in ts_matrix.columns:
            p_val = sig_stations.loc[stn, p_col]
            
            # Significance mapping matching the original script
            if p_val <= 0.001:
                alpha = 1.0
                lw = 1.5
                ms = 8
                marker = 'D'
            elif p_val <= 0.01:
                alpha = 1.0
                lw = 1.2
                ms = 6
                marker = 's'
            else:
                alpha = 1.0
                lw = 1.0
                ms = 5
                marker = 'o'
                
            ax.plot(ts_matrix.index, ts_matrix[stn], marker=marker, color=base_color, 
                    alpha=alpha, linewidth=lw, markersize=ms)
                    
    ax.set_title(target_division, fontsize=16, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.set_xlabel('Year', fontsize=18)
    ax.set_ylabel(parameter.replace('_', ' '), fontsize=18)
    
    # Super title matching the original script's naming style
    suptitle_text = f"{pc_name} vs {parameter.replace('_', ' ')} Correlation Time Series"
    fig.suptitle(suptitle_text, fontsize=18, fontweight='bold', y=1.02)
    
    # Legend matching the original script's style
    custom_lines = [
        mlines.Line2D([0], [0], color='gray', marker='D', lw=1.5, alpha=1.0, markersize=8, label='Highest Significance (p ≤ 0.001)'),
        mlines.Line2D([0], [0], color='gray', marker='s', lw=1.0, alpha=1.0, markersize=6, label='Medium Significance (p ≤ 0.01)'),
        mlines.Line2D([0], [0], color='gray', marker='o', lw=1.0, alpha=1.0, markersize=5, label='Lower Significance (p ≤ 0.05)')
    ]
    
    ax.legend(handles=custom_lines, loc='upper right', frameon=True, fontsize=16)
    
    plt.tight_layout()
    
    out_dir = ProjectPaths.FIGURES_DIR / "seasonal_plots" / "time_series_by_region"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{pc_name}_{parameter}_ts_suo_nada.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved Suo Nada plot to {out_path}")

if __name__ == '__main__':
    main()

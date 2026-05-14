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
    # Parameters for test
    pc_name = "PC1"
    parameter = "Spring_1_CHLA"
    
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
        
    print(f"Found {len(sig_stations)} significant stations.")
    
    # Get time series matrix
    print(f"Building time series matrix for {parameter}...")
    season = "Summer"
    saisuipoin = 2
    raw_param = "chlorophyl"
    ts_matrix = get_time_series_matrix(merged_df, raw_param, season, saisuipoin)
    
    # Get station regions
    station_regions = merged_df[['zettaicode', 'division']].drop_duplicates().set_index('zettaicode')['division']
    
    # Map significant stations to their regions
    sig_station_regions = station_regions[station_regions.index.isin(sig_stations.index)].dropna()
    unique_regions = sig_station_regions.unique()
    
    if len(unique_regions) == 0:
        print("No valid regions found for significant stations.")
        return
        
    print(f"Plotting for regions: {unique_regions}")
    
    # Dynamic grid calculation
    n_regions = len(unique_regions)
    n_cols = min(3, n_regions)
    n_rows = math.ceil(n_regions / n_cols)
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 4 * n_rows), sharex=True, sharey=True)
    if n_regions == 1:
        axes = np.array([axes])
    axes = axes.flatten()
    
    cmap = cm.get_cmap('tab10')
    
    for i, region in enumerate(unique_regions):
        ax = axes[i]
        base_color = cmap(i % 10)
        
        region_stns = sig_station_regions[sig_station_regions == region].index
        
        for stn in region_stns:
            if stn in ts_matrix.columns:
                p_val = sig_stations.loc[stn, p_col]
                
                # Significance mapping
                if p_val <= 0.001:
                    alpha = 1.0
                    lw = 1.5
                    ms = 8
                    marker = 'D'
                elif p_val <= 0.01:
                    alpha = 1
                    lw = 1.2
                    ms = 6
                    marker = 's'
                else:
                    alpha = 1
                    lw = 1
                    ms = 5
                    marker = 'o'
                    
                ax.plot(ts_matrix.index, ts_matrix[stn], marker=marker, color=base_color, 
                        alpha=alpha, linewidth=lw, markersize=ms)
                        
        ax.set_title(region, fontsize=18, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.5)
        
    # Hide unused subplots
    for j in range(len(unique_regions), len(axes)):
        fig.delaxes(axes[j])
        
    # Set common labels appropriately
    for j in range(len(unique_regions)):
        # x-labels only on bottom row of the visible grid or if the subplot below it is deleted
        if j >= n_regions - n_cols:
            axes[j].set_xlabel('Year', fontsize=18)
        # y-labels only on leftmost column
        if j % n_cols == 0:
            axes[j].set_ylabel(parameter.replace('_', ' '), fontsize=18)
            
    # Super title
    suptitle_text = f"{pc_name} vs {parameter.replace('_', ' ')} Correlation Time Series"
    fig.suptitle(suptitle_text, fontsize=20, fontweight='bold', y=1.05)
    
    # Legend
    custom_lines = [
        mlines.Line2D([0], [0], color='gray', marker='D', lw=1.5, alpha=1.0, markersize=8, label='Highest Significance (p ≤ 0.001)'),
        mlines.Line2D([0], [0], color='gray', marker='s', lw=1.0, alpha=1.0, markersize=6, label='Medium Significance (p ≤ 0.01)'),
        mlines.Line2D([0], [0], color='gray', marker='o', lw=1.0, alpha=1.0, markersize=5, label='Lower Significance (p ≤ 0.05)')
    ]
    
    # Adjust legend position based on layout
    fig.legend(handles=custom_lines, loc='upper center', bbox_to_anchor=(0.5, 1.0), 
               ncol=3, fontsize=18, frameon=False)
    
    plt.tight_layout()
    
    out_dir = ProjectPaths.FIGURES_DIR / "seasonal_plots" / "time_series_by_region"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{pc_name}_{parameter}_ts_regions.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved test plot to {out_path}")

if __name__ == '__main__':
    main()

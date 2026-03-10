#!/usr/bin/env python3
"""
Generate a 16:9 heatmap of DO across all years and all stations for four seasons.
Outputs one figure for the surface layer and one for the bottom layer.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys

# Ensure local scripts are importable based on script location
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from scripts.paths import ProjectPaths
from scripts.mapping_config import MappingConfig

def create_seasonal_heatmaps():
    layers = ['surface', 'bottom']
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    
    # Retrieve standardized visual mapping for dissolved oxygen
    do_settings = MappingConfig.get_var_settings('do_')
    cmap = do_settings['cmap']
    vmin = do_settings['vmin']
    vmax = do_settings['vmax']
    cbar_label = do_settings['label']
    
    # Ensure pure style for heatmaps
    sns.set_style("white")
    
    # Enforce directory existence
    ProjectPaths.ensure_directories()
    
    # Load station coordinates for spatial sorting (West to East)
    merged_gdf = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    station_longitudes = merged_gdf[['zettaicode', 'longitude']].drop_duplicates()
    station_longitudes['zettaicode'] = station_longitudes['zettaicode'].astype(str)
    station_longitudes.set_index('zettaicode', inplace=True)
    
    for layer in layers:
        # Create a single figure matching a 16:9 PPT slide ratio 
        fig, axes = plt.subplots(2, 2, figsize=(16, 9))
        axes = axes.flatten()
        
        # Add overarching title
        fig.suptitle(f'Interannual DO Variability by Season ({layer.capitalize()} Layer)', 
                     fontsize=18, fontweight='bold', y=0.98)
        
        for i, season in enumerate(seasons):
            ax = axes[i]
            
            # Form path to processed data using the project's seasonal subset helper
            subset_dir = ProjectPaths.get_subset_dir(season, layer)
            data_file = subset_dir / "yearly_do_df.csv"
            
            if data_file.exists():
                df = pd.read_csv(data_file, index_col=0)
                df.index = df.index.astype(str)
                
                # Sort stations by longitude (West to East)
                # We align the existing index with the known longitudes
                sorted_index = station_longitudes.reindex(df.index).sort_values('longitude').index
                df = df.reindex(sorted_index)
                
                # Generate heatmap
                # xticklabels=False and yticklabels=False suppress the individual tick markers
                sns.heatmap(df, ax=ax, cmap=cmap, vmin=vmin, vmax=vmax, 
                            cbar=True, cbar_kws={'aspect': 40, 'label': cbar_label},
                            xticklabels=False, yticklabels=False)
                
                ax.set_title(f'{season}', fontsize=14, fontweight='bold')
                
                # General axes titles rather than row/col individual labels
                ax.set_xlabel('Year | \u2192', fontsize=12)
                ax.set_ylabel('\u2193 | Stations', fontsize=12)
            else:
                # Handle missing sub-sets cleanly
                ax.text(0.5, 0.5, f'[ Data not found: {data_file.name} ]', 
                        ha='center', va='center', fontsize=12, color='gray')
                ax.set_title(f'{season}', fontsize=14, fontweight='bold')
                
                ax.set_xticks([])
                ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_color('lightgray')

        # Tight layout to maximize space usage. Rect prevents overlapping with the suptitle
        plt.tight_layout(rect=[0, 0, 1, 0.96])  
        
        out_file = ProjectPaths.FIGURES_DIR / f'29_seasonal_heatmap_do_{layer}.png'
        plt.savefig(out_file, dpi=300, facecolor='white', bbox_inches='tight')
        print(f"Saved generated figure to: {out_file}")
        
        plt.close()

if __name__ == "__main__":
    create_seasonal_heatmaps()

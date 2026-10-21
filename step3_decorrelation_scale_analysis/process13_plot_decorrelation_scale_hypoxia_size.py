#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Process 13: Decorrelation scale map (as in step3 process12) where the marker size
represents each station's hypoxia frequency. Hypoxia frequency and marker-size logic
are copied from step2 process12_hypoxia_frequency_map.py:
  - Summer season, saisuipoin == 2 (surface sampling), division filtered by watermass_name
  - frequency = (# years with any DO in [0, 2] mg/L) / (# years with data) * 100
  - marker size = (frequency * 2.4 + 24) * zoom_factor
Color still shows the decorrelation scale (km).

Usage: python process13_plot_decorrelation_scale_hypoxia_size.py --division "Tokyo Bay"
"""
import sys
import argparse
import warnings
from pathlib import Path

CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import cartopy.crs as ccrs
import cartopy.feature as cfeature

warnings.filterwarnings('ignore')

from utils.data_loader import load_and_process_data
from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

TARGET_SEASON = 'Summer'


def compute_hypoxia_frequency(merged_gdf, division):
    """Same calculation as step2 process12 (Figure 2)."""
    df = merged_gdf[(merged_gdf['season'] == TARGET_SEASON) & (merged_gdf['saisuipoin'] == 2)].copy()
    df['do_'] = pd.to_numeric(df['do_'], errors='coerce')
    df = df.dropna(subset=['do_'])
    if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay']:
        division = 'Ise Bay'  # step2 uses the 'Ise Bay' watermass name
    if division in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        df = df[df['watermass_name'] == division]
    else:
        df = df[df['division'] == division]
    if df.empty:
        return pd.DataFrame(columns=['zettaicode', 'frequency'])

    def calc_freq(group):
        total_years = group['year'].nunique()
        cond_years = group[(group['do_'] >= 0.0) & (group['do_'] <= 2.0)]['year'].nunique()
        return (cond_years / total_years) * 100

    freq_df = df.groupby(['zettaicode', 'longitude', 'latitude']).apply(calc_freq).reset_index(name='frequency')
    freq_df['zettaicode_str'] = freq_df['zettaicode'].astype(str).str.zfill(8)
    return freq_df[['zettaicode_str', 'frequency']]


def plot_map(division, results_df, freq_df, merged_gdf):
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))

    coords = merged_gdf[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').copy()
    coords['zettaicode_str'] = coords['zettaicode'].astype(str).str.zfill(8)
    plot_data = coords.merge(results_df, left_on='zettaicode_str', right_on='Station_ID')
    plot_data = plot_data.merge(freq_df, on='zettaicode_str', how='inner')
    if plot_data.empty:
        print(f"No stations with both decorrelation scale and hypoxia frequency for {division}")
        return

    map_extent = MappingConfig.get_dynamic_extent(division, plot_data=plot_data)
    fig_width, fig_height = MappingConfig.get_dynamic_figsize(map_extent, base_width=10)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)

    try:
        db_division = 'Ise Bay' if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay'] else division
        name = {'Tokyo Bay': 'Tokyobay_boundary.shp', 'Ise Bay': 'Isebay_boundary.shp'}.get(
            db_division, 'Setonaikai_boundary.shp')
        path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / name
        if path.exists():
            lb = gpd.read_file(path)
            if lb.crs != "EPSG:4326":
                lb = lb.to_crs("EPSG:4326")
            lb.plot(ax=ax, facecolor=MappingConfig.COLOR_LAND, edgecolor=MappingConfig.COLOR_LAND_EDGE,
                    linewidth=MappingConfig.LINEWIDTH_LAND, transform=ccrs.PlateCarree(),
                    zorder=MappingConfig.ZORDER_LAND)
    except Exception as e:
        print(f"Could not load custom boundary for {division}: {e}")

    extent_width = map_extent[1] - map_extent[0]
    zoom_factor = max(4.5 / extent_width, 1.0)
    marker_sizes = (plot_data['frequency'] * 2.4 + 24) * zoom_factor

    sc = ax.scatter(
        plot_data['longitude'], plot_data['latitude'],
        c=plot_data['Decorrelation_Scale_km'], cmap='viridis',
        s=marker_sizes, edgecolors='k', linewidths=0.5,
        transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_PREDICTED
    )

    MappingConfig.apply_gridlines(ax)
    ax.set_extent(map_extent, crs=ccrs.PlateCarree())
    plt.title(f'{division}: Decorrelation Scale (km)\nMarker size = Hypoxia Frequency (0-2 mg/L, {TARGET_SEASON})')

    # Size legend (same size formula)
    legend_handles = [
        Line2D([0], [0], marker='o', linestyle='', markerfacecolor='lightgray', markeredgecolor='k',
               markersize=np.sqrt((f * 2.4 + 24) * zoom_factor), label=f'{f}%')
        for f in (0, 25, 50, 75, 100)
    ]
    legend_loc = 'upper right' if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay'] else 'lower right'
    ax.legend(handles=legend_handles, title='Hypoxia freq.', loc=legend_loc, labelspacing=1.2,
              framealpha=0.9).set_zorder(MappingConfig.ZORDER_PREDICTED + 10)

    plt.subplots_adjust(bottom=0.15)
    cbar_ax = fig.add_axes([0.25, 0.05, 0.5, 0.03])
    cbar = fig.colorbar(sc, cax=cbar_ax, orientation='horizontal')
    cbar.set_label('Decorrelation Scale (km)')

    div_folder = division.replace(' ', '_').lower()
    figures_dir = ProjectPaths.FIGURES_DIR / STEP_DIR / SCRIPT_NAME / div_folder
    figures_dir.mkdir(parents=True, exist_ok=True)
    out_img = figures_dir / f"{div_folder}_decorrelation_scale_hypoxia_size.png"
    plt.savefig(out_img, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved plot for {division} to: {out_img}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--division', type=str, required=True)
    args, _ = parser.parse_known_args()
    division = args.division
    div_folder = division.replace(' ', '_').lower()

    ProjectPaths.ensure_directories()
    merged_gdf = load_and_process_data(force_reload=False)

    csv_file = (ProjectPaths.PROCESSED_DATA_DIR / STEP_DIR / "process11_calculate_decorrelation_scale_per_bay"
                / div_folder / f"{div_folder}_decorrelation_scale.csv")
    if not csv_file.exists():
        print(f"Error: Required data file not found: {csv_file}")
        return
    df = pd.read_csv(csv_file)
    df['Station_ID'] = df['Station_ID'].astype(str).str.zfill(8)

    freq_df = compute_hypoxia_frequency(merged_gdf, division)
    print(f"Hypoxia frequency computed for {len(freq_df)} stations in {division}")
    plot_map(division, df, freq_df, merged_gdf)


if __name__ == "__main__":
    main()

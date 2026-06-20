# -*- coding: utf-8 -*-
"""
44_station_timeseries_plotting.py

Standalone script for plotting raw time series of environmental parameters
by water mass division. Extracted from notebook 44_driver_comparison_by_trend.ipynb.

This script:
  1. Loads the merged dataset and calculates hypoxia trends (ΔP).
  2. Groups stations into "Worsening Local" vs "Improving Regional".
  3. Plots time series of 21 parameters across 9 water mass divisions,
     with stations colored by their group membership.

Usage:
    conda activate sis_analysis
    python notebooks/44_station_timeseries_plotting.py
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend: save to file without GUI windows
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import os
import sys
import yaml
from pathlib import Path
from matplotlib.lines import Line2D

# ---------------------------------------------------------------------------
# 0. Project Setup
# ---------------------------------------------------------------------------
# Resolve project root and add to sys.path
cwd = Path(os.getcwd())
if (cwd / 'params.yaml').exists():
    project_root = cwd
else:
    project_root = cwd.parent

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
if str(project_root / 'scripts') not in sys.path:
    sys.path.append(str(project_root / 'scripts'))

from utils.paths import ProjectPaths
from scripts.data_loader import load_and_process_data

# Apply the global project style
style_path = project_root / 'project_style.mplstyle'
if style_path.exists():
    plt.style.use(str(style_path))

# Load parameters
with open(project_root / 'params.yaml', 'r') as f:
    params = yaml.safe_load(f)

TARGET_REGION = params['mapping']['target_region']
REGION_COLUMN = params['mapping']['region_column']
REP_MONTH_SUMMER = params['seasonal_subsets']['representative_months']['Summer']

print(f"Target Region: {TARGET_REGION}")

# ---------------------------------------------------------------------------
# 1. Data Preparation and Trend Calculation
# ---------------------------------------------------------------------------
LOW_DO_THRESHOLD = 5.0

print("Loading data...")
merged_gdf = load_and_process_data(force_reload=False)
merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

# Filter for Target Region and Summer Bottom
df = merged_gdf[merged_gdf[REGION_COLUMN] == TARGET_REGION].copy()
summer_bottom = df[
    (df['surveymont'] == REP_MONTH_SUMMER) &
    (df['saisuipoin'] == 2)
].copy()
summer_bottom['do_'] = pd.to_numeric(summer_bottom['do_'], errors='coerce')
summer_bottom = summer_bottom.dropna(subset=['do_'])

# Pivot data
pivot_df = summer_bottom.pivot_table(index='zettaicode', columns='year', values='do_', aggfunc='mean')
pivot_df.index = pivot_df.index.astype(str).str.zfill(8)

# Calculate Trend
years = pivot_df.columns.astype(int)
hist_years = [y for y in years if 1981 <= y <= 2013]
recent_years = [y for y in years if 2014 <= y <= 2023]

p_hist = (pivot_df[hist_years] < LOW_DO_THRESHOLD).sum(axis=1) / 33
p_recent = (pivot_df[recent_years] < LOW_DO_THRESHOLD).sum(axis=1) / 10
delta = p_recent - p_hist

# Coordinates
coords = summer_bottom.groupby('zettaicode')[['latitude', 'longitude']].first()

# Decorrelation Scale
subset_dir = ProjectPaths.get_subset_dir('Summer', 'bottom')
decorr_file = subset_dir / "stations_decorrelation_scale.csv"
if decorr_file.exists():
    df_decorr = pd.read_csv(decorr_file, dtype={'Station_ID': str})
    df_decorr['Station_ID'] = df_decorr['Station_ID'].str.zfill(8)
else:
    print(f"Warning: {decorr_file} not found.")
    df_decorr = pd.DataFrame(columns=['Station_ID', 'Decorrelation_Scale_km'])

# Combine
map_df = pd.DataFrame({
    'delta': delta,
    'p_recent': p_recent,
    'lat': coords['latitude'],
    'lon': coords['longitude']
}).dropna().reset_index().rename(columns={'zettaicode': 'Station_ID'})

stats_df = map_df.merge(
    df_decorr[['Station_ID', 'Decorrelation_Scale_km']],
    on='Station_ID',
    how='inner'
)
print(f"Total stations with trend and decorrelation data: {len(stats_df)}")

# ---------------------------------------------------------------------------
# 2. Station Selection and Grouping
# ---------------------------------------------------------------------------
# Group 1 (Local & Worsening): Decorrelation_Scale_km < 20 & delta > 0
# Group 2 (Regional & Improving): Decorrelation_Scale_km > 10 & delta < -0.2

group1_mask = (stats_df['Decorrelation_Scale_km'] < 20) & (stats_df['delta'] > 0)
group2_mask = (stats_df['Decorrelation_Scale_km'] > 10) & (stats_df['delta'] < -0.2)

stats_df['Group'] = 'Other'
stats_df.loc[group1_mask, 'Group'] = 'Group 1 (Local & Worsening)'
stats_df.loc[group2_mask, 'Group'] = 'Group 2 (Regional & Improving)'

selected_stations = stats_df[stats_df['Group'] != 'Other'].copy()
print(f"Group 1 count: {len(selected_stations[selected_stations['Group'] == 'Group 1 (Local & Worsening)'])}")
print(f"Group 2 count: {len(selected_stations[selected_stations['Group'] == 'Group 2 (Regional & Improving)'])}")

# ---------------------------------------------------------------------------
# 3. Time Series Visualization by Water Mass Division
# ---------------------------------------------------------------------------

# List of target divisions exactly as they appear in the data
target_divisions = [
    'Suo Nada', 'Hiroshima Bay', 'Hiuchi Nada', 'Bingo Nada',
    'Bisan Seto', 'Harima Nada', 'Osaka Bay', 'Kii Channel', 'Aki Nada'
]

# Mapping of the requested parameters with units
ts_params = [
    {'title': 'Surface Summer DO', 'col': 'do_', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer DO', 'col': 'do_', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Summer SST', 'col': 'wtemp', 'layer': 1, 'unit': '°C'},
    {'title': 'Summer SBT', 'col': 'wtemp', 'layer': 2, 'unit': '°C'},
    {'title': 'Summer SSS', 'col': 'salt', 'layer': 1, 'unit': 'PSU'},
    {'title': 'Summer SBS', 'col': 'salt', 'layer': 2, 'unit': 'PSU'},
    {'title': 'Summer Stratification', 'col': 'stratification', 'layer': 2, 'unit': 'kg/m³'},
    {'title': 'Surface Summer Chl-a', 'col': 'chlorophyl', 'layer': 1, 'unit': 'μg/L'},
    {'title': 'Bottom Summer Chl-a', 'col': 'chlorophyl', 'layer': 2, 'unit': 'μg/L'},
    {'title': 'Surface Summer TN', 'col': 'tn', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer TN', 'col': 'tn', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer TP', 'col': 'tp', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer TP', 'col': 'tp', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer DIN', 'col': 'din', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer DIN', 'col': 'din', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer DIP', 'col': 'po4p', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer DIP', 'col': 'po4p', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer COD', 'col': 'cod', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer COD', 'col': 'cod', 'layer': 2, 'unit': 'mg/L'},
    {'title': 'Surface Summer DOC', 'col': 'doc', 'layer': 1, 'unit': 'mg/L'},
    {'title': 'Bottom Summer DOC', 'col': 'doc', 'layer': 2, 'unit': 'mg/L'}
]

# Extract division information
st_group_map = selected_stations.set_index('Station_ID')['Group'].to_dict()
st_division_map = merged_gdf[merged_gdf['zettaicode'].isin(st_group_map.keys())][
    ['zettaicode', 'division']
].drop_duplicates().set_index('zettaicode')['division'].to_dict()

# Filter data for summer
summer_data = merged_gdf[
    (merged_gdf['surveymont'] == REP_MONTH_SUMMER) &
    (merged_gdf['zettaicode'].isin(st_group_map.keys()))
].copy()

# Add calculated DIN if necessary
if 'din' not in summer_data.columns:
    nh4 = pd.to_numeric(summer_data['nh4n'], errors='coerce').fillna(0)
    no2 = pd.to_numeric(summer_data['no2n'], errors='coerce').fillna(0)
    no3 = pd.to_numeric(summer_data['no3n'], errors='coerce').fillna(0)
    summer_data['din'] = nh4 + no2 + no3
    all_nan = summer_data['nh4n'].isna() & summer_data['no2n'].isna() & summer_data['no3n'].isna()
    summer_data.loc[all_nan, 'din'] = np.nan

# Consistent coloring
colors = {
    'Group 1 (Local & Worsening)': 'indianred',
    'Group 2 (Regional & Improving)': 'steelblue'
}

# Global legend elements
legend_elements = [
    Line2D([0], [0], color='indianred', marker='o', markersize=10, label='Group 1 (Worsening)', linewidth=2),
    Line2D([0], [0], color='steelblue', marker='o', markersize=10, label='Group 2 (Improving)', linewidth=2)
]

print(f"\nPlotting {len(ts_params)} parameters across {len(target_divisions)} water mass divisions...")

for param in ts_params:
    fig, axes = plt.subplots(3, 3, figsize=(24, 15), sharex=True, sharey=True)

    # Title includes the unit
    fig.suptitle(f"{param['title']} [{param['unit']}]", fontsize=30, fontweight='bold', y=0.96)

    # Global Legend at top right
    fig.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.98, 0.965),
               fontsize=22, frameon=False, ncol=1)

    axes = axes.flatten()
    layer_data = summer_data[summer_data['saisuipoin'] == param['layer']].copy()
    layer_data[param['col']] = pd.to_numeric(layer_data[param['col']], errors='coerce')

    for i, div in enumerate(target_divisions):
        ax = axes[i]
        div_stations = [s for s, d in st_division_map.items() if d == div]

        for st in div_stations:
            st_df = layer_data[layer_data['zettaicode'] == st].sort_values('year')
            if st_df.empty or st_df[param['col']].isna().all():
                continue

            group = st_group_map.get(st)
            if not group:
                continue

            ax.plot(st_df['year'], st_df[param['col']], color=colors[group],
                    marker='o', markersize=4, alpha=0.6, linewidth=2)

        ax.set_title(div, fontsize=24, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.5)

        if i >= 6:
            ax.set_xlabel('Year', fontsize=24)
        if i % 3 == 0:
            # Y-axis label only contains the parameter name
            ax.set_ylabel(param['title'], fontsize=24)

        ax.tick_params(labelsize=24)

    # Cleanup unused axes
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    # Save each figure
    safe_title = param['title'].replace(' ', '_').replace('-', '_')
    output_dir = ProjectPaths.FIGURES_DIR / "44_station_timeseries"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"timeseries_{safe_title}_{TARGET_REGION.replace(' ', '_')}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)  # Free memory instead of displaying
    print(f"  Saved: {output_path.name}")

print("\nAll time series plots complete.")

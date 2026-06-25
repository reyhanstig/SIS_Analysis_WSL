# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Auto-generated from: 42_hypoxia_tendecy_per_station.ipynb
# Generated on: 2026-05-05T19:56:00
# This script was converted from a Jupyter Notebook.
# Markdown cells have been converted to comments.

# The goal now is to see the hypoxia trend for each station points. This means whether summer bottom hypoxia happens more frequently on late year or recent years. What I'm looking for are places where hypoxia is getting worse. This means more occurrence in recent years. 

# # Stage 4.2: Hypoxia Tendency per Station
# 
# This notebook visualizes the temporal trend of **Summer Bottom Dissolved Oxygen (DO)** for every station in the study area. 
# 
# ### Goal:
# Identify stations where hypoxia is becoming more frequent or severe over time. 
# - **X-axis**: Year
# - **Y-axis**: Station ID (`zettaicode`)
# - **Color (Z-axis)**: DO Value (mg/L). 
# 
# By sorting stations geographically or by their mean DO, we can identify spatial clusters of worsening hypoxia.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- BOILERPLATE INJECTED BY AGENT ---
import os
import sys
import pandas as pd
import logging
import matplotlib.pyplot as plt
from pathlib import Path

CURRENT_SCRIPT = Path(__file__).resolve()
# Fix namespace shadowing by inserting project root at index 0
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
import shutil
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
import shutil
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
if PROCESSED_DATA_DIR.exists():
    shutil.rmtree(PROCESSED_DATA_DIR, ignore_errors=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')

param_file = CURRENT_SCRIPT.parent / f"step{step_num}_parameter.csv"
PARAMS = {}
if param_file.exists():
    df_params = pd.read_csv(param_file)
    if 'parameter_name' in df_params.columns and 'value' in df_params.columns:
        for _, row in df_params.iterrows():
            PARAMS[row['parameter_name']] = row['value']
# -------------------------------------
plt.style.use('../project_style.mplstyle')
import seaborn as sns
import sys
import os
import yaml
from pathlib import Path
from scipy import stats

# Resolve project root and add to sys.path
cwd = Path(os.getcwd())
if (cwd / 'params.yaml').exists():
    project_root = cwd
else:
    project_root = cwd.parent
    
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from utils.data_loader import load_and_process_data

print("Project root:", project_root)


# Load the pre-processed data
merged_gdf = load_and_process_data(force_reload=False)

# Load parameters from params.yaml
with open(project_root / 'params.yaml', 'r') as f:
    params = yaml.safe_load(f)

TARGET_REGION = params['mapping']['target_region']
REGION_COLUMN = params['mapping']['region_column']
REP_MONTH_SUMMER = params['seasonal_subsets']['representative_months']['Summer']

print(f"Target Region: {TARGET_REGION} (Column: {REGION_COLUMN})")
print(f"Representative Summer Month: {REP_MONTH_SUMMER}")

# Apply Regional Filtering
df = merged_gdf[merged_gdf[REGION_COLUMN] == TARGET_REGION].copy()

# Filter for Summer Bottom DO
summer_bottom = df[
    (df['surveymont'] == REP_MONTH_SUMMER) &
    (df['saisuipoin'] == 2)
].copy()

# Ensure DO is numeric and drop NaNs
summer_bottom['do_'] = pd.to_numeric(summer_bottom['do_'], errors='coerce')
summer_bottom = summer_bottom.dropna(subset=['do_'])

print(f"Total observations: {len(summer_bottom)}")
print(f"Number of unique stations: {summer_bottom['zettaicode'].nunique()}")


# ## 1. Create Temporal-Spatial Matrix
# 
# We pivot the data to create a matrix where each row is a station and each column is a year.

# Pivot data: Rows = zettaicode, Cols = year, Values = do_
pivot_df = summer_bottom.pivot_table(
    index='zettaicode',
    columns='year',
    values='do_',
    aggfunc='mean'
)

# Clean index: ensure 8-digit strings
pivot_df.index = pivot_df.index.astype(str).str.zfill(8)

# Sort stations by their mean DO (descending)
station_mean_do = pivot_df.mean(axis=1).sort_values(ascending=False)
pivot_df = pivot_df.loc[station_mean_do.index]

pivot_df.head()


# ## 2. Visualize Hypoxia Tendency
# 
# The following heatmap shows the DO levels over time. 
# - **Blue/Cool colors**: High DO (Healthy)
# - **Red/Warm colors**: Low DO (Hypoxic)
# - **Empty space (White)**: Missing data

# Setup for heatmap
plt.figure(figsize=(20, 30))
sns.heatmap(
    pivot_df, 
    cmap='RdYlBu', 
    center=4.0,  # Center around the hypoxic threshold
    cbar_kws={'label': 'Dissolved Oxygen (mg/L)'},
    linewidths=0.01,
    linecolor='gray'
)

plt.title(f'Hypoxia Status Over Time per Station - {TARGET_REGION}')
plt.ylabel('Station (zettaicode) - Sorted by Mean DO (High to Low)')
plt.xlabel('Year')

# Save the plot
output_path = project_root / 'figures' / f'hypoxia_status_comparison_{TARGET_REGION.replace(" ", "_")}.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"Comparison plot saved to: {output_path}")

plt.savefig(OUTPUT_DIR / f'plot_5056.png', bbox_inches='tight', dpi=300)
plt.close()


# ## 3. Analyze Trends with Regression
# 
# We can calculate the linear regression slope for each station to see if it's generally getting worse (negative slope) or better (positive slope).

def calculate_slope(row):
    valid_mask = ~row.isna()
    if valid_mask.sum() < 5:  # Require at least 5 years of data
        return np.nan
    
    years = row.index[valid_mask].astype(float)
    values = row[valid_mask].values
    slope, intercept, r_value, p_value, std_err = stats.linregress(years, values)
    return slope

slopes = pivot_df.apply(calculate_slope, axis=1).dropna()

plt.figure(figsize=(10, 6))
sns.histplot(slopes, bins=20, kde=True, color='purple')
plt.axvline(0, color='red', linestyle='--')
plt.title(f'Distribution of DO Trends (Slopes) across Stations - {TARGET_REGION}')
plt.xlabel('Slope (mg/L per Year)')
plt.ylabel('Count')
plt.savefig(OUTPUT_DIR / f'plot_5917.png', bbox_inches='tight', dpi=300)
plt.close()

worsening = slopes[slopes < 0]
improving = slopes[slopes > 0]

print(f"Stations with worsening trend: {len(worsening)}")
print(f"Stations with improving trend: {len(improving)}")


# ## 4. Correlation with Decorrelation Scale
# 
# Does the temporal trend correlate with the decorrelation scale?
# (Assuming we have loaded the decorrelation results from previous steps)

# For now, let's just save the slopes for later integration
slopes_df = slopes.to_frame(name='do_slope_per_year')
slopes_df.index.name = 'zettaicode'

output_csv = project_root / 'data' / 'processed' / 'hypoxia_tendency_slopes.csv'
slopes_df.to_csv(output_csv)
print(f"Slopes saved to: {output_csv}")

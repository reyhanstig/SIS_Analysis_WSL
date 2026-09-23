# %% [markdown]
# # GAM Sandbox: Checking Linearity of Environmental Drivers vs. DO
# This script iterates through all parameters defined in Step 5 (`step5_ts_parameters.csv`),
# matches them against Bottom DO for the same season, and fits a Generalized Additive Model (GAM)
# to check for linearity using Effective Degrees of Freedom (EDF).

# %%
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pygam import LinearGAM, s
import warnings

# Suppress pygam warnings for cleaner output
warnings.filterwarnings('ignore')

# 1. Setup paths and imports
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.data_loader import load_and_process_data
import gsw

# %%
# 2. Load Real Dataset
print("Loading real dataset...")
merged_gdf = load_and_process_data(force_reload=False)

# To keep the sandbox fast and relevant, we filter for a specific region (e.g., Tokyo Bay)
# You can change this to 'Seto Inland Sea' or 'Ise Bay' as needed.
target_region = 'Tokyo Bay'
print(f"Filtering data for {target_region}...")
if target_region in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
    merged_gdf = merged_gdf[merged_gdf['watermass_name'] == target_region].copy()
else:
    merged_gdf = merged_gdf[merged_gdf['division'] == target_region].copy()

# Ensure density is calculated for stratification
merged_gdf['salt'] = pd.to_numeric(merged_gdf['salt'], errors='coerce')
merged_gdf['wtemp'] = pd.to_numeric(merged_gdf['wtemp'], errors='coerce')
merged_gdf['density'] = gsw.rho(merged_gdf['salt'], merged_gdf['wtemp'], 0) - 1000

# Calculate DIN if missing
nh4 = pd.to_numeric(merged_gdf['nh4n'], errors='coerce').fillna(0)
no2 = pd.to_numeric(merged_gdf['no2n'], errors='coerce').fillna(0)
no3 = pd.to_numeric(merged_gdf['no3n'], errors='coerce').fillna(0)
merged_gdf['din'] = nh4 + no2 + no3
merged_gdf.loc[merged_gdf['nh4n'].isna() & merged_gdf['no2n'].isna() & merged_gdf['no3n'].isna(), 'din'] = np.nan

# %%
# 3. Load parameters from step 5
params_df = pd.read_csv(project_root / 'step5_environmental_factor_correlation_analysis' / 'step5_ts_parameters.csv')
env_params = params_df[~params_df['col'].str.contains('do_')].copy()

out_dir = project_root / "figures" / "step0_sandbox" / "72_check_linearity_with_gam"
out_dir.mkdir(parents=True, exist_ok=True)
print(f"Output directory ready at: {out_dir}")

# %%
# 4. Iterate over all permutations and fit GAM
print(f"\nTesting {len(env_params)} parameter permutations against Bottom DO...")

for _, row in env_params.iterrows():
    param_title = row['title']
    param_col = row['col']
    layer = row['layer']
    season = row['season']
    
    # Filter data for the specific season
    season_data = merged_gdf[merged_gdf['season'] == season].copy()
    
    # Extract DO (Targeting Bottom DO as the standard dependent variable)
    do_data = season_data[season_data['saisuipoin'] == 2][['zettaicode', 'surveyyear', 'do_']]
    do_data = do_data.rename(columns={'do_': 'DO'})
    do_data['DO'] = pd.to_numeric(do_data['DO'], errors='coerce')
    
    # Extract Env factor
    if param_col == 'stratification':
        surf = season_data[season_data['saisuipoin'] == 1].groupby(['zettaicode', 'surveyyear'])['density'].mean()
        bot = season_data[season_data['saisuipoin'] == 2].groupby(['zettaicode', 'surveyyear'])['density'].mean()
        env_data = (bot - surf).reset_index().rename(columns={'density': param_col})
    else:
        env_data = season_data[season_data['saisuipoin'] == layer][['zettaicode', 'surveyyear', param_col]]
        env_data[param_col] = pd.to_numeric(env_data[param_col], errors='coerce')
        
    # Aggregate to prevent duplicates (mean per station-year)
    do_data = do_data.groupby(['zettaicode', 'surveyyear'])['DO'].mean().reset_index()
    env_data = env_data.groupby(['zettaicode', 'surveyyear'])[param_col].mean().reset_index()
    
    # Merge on station and year
    paired = pd.merge(do_data, env_data, on=['zettaicode', 'surveyyear']).dropna(subset=['DO', param_col])
    
    # Remove extreme outliers (top/bottom 1%) to prevent GAM from blowing up on noise
    if len(paired) > 50:
        q_low = paired[param_col].quantile(0.01)
        q_high = paired[param_col].quantile(0.99)
        paired = paired[(paired[param_col] >= q_low) & (paired[param_col] <= q_high)]
    
    if len(paired) < 30:
        print(f"[-] Skipping '{param_title}' (insufficient data: {len(paired)} points)")
        continue
        
    X = paired[[param_col]].values
    y = paired['DO'].values
    
    try:
        # Fit GAM
        gam_smooth = LinearGAM(s(0)).fit(X, y)
        edf = gam_smooth.statistics_['edof_per_coef'][0]
        
        # Determine linearity
        linearity_str = "LINEAR" if edf < 1.5 else "NON-LINEAR"
        print(f"[+] Processed '{param_title}' | EDF: {edf:.2f} ({linearity_str}) | n={len(paired)}")
        
        # Plot
        fig, ax = plt.subplots(figsize=(8, 6))
        XX = gam_smooth.generate_X_grid(term=0)
        ax.plot(XX[:, 0], gam_smooth.partial_dependence(term=0, X=XX), color='indianred', linewidth=3)
        ax.plot(XX[:, 0], gam_smooth.partial_dependence(term=0, X=XX, width=.95)[1], c='gray', ls='--', alpha=0.5)
        ax.scatter(X, y - gam_smooth.coef_[-1], alpha=0.2, edgecolor='k')
        
        ax.set_title(f'GAM Partial Dependence: {param_title} vs Bottom DO\nEDF: {edf:.2f} ({linearity_str}) | Region: {target_region}', fontweight='bold')
        ax.set_xlabel(param_title)
        ax.set_ylabel(f"Partial Effect on Bottom DO")
        ax.grid(True, linestyle='--', alpha=0.6)
        
        safe_title = param_title.replace(' ', '_').replace('/', '_')
        plt.tight_layout()
        out_path = out_dir / f"gam_{safe_title}.png"
        plt.savefig(out_path, dpi=300)
        plt.close()
        
    except Exception as e:
        print(f"[!] Error fitting GAM for {param_title}: {e}")

print(f"\nAll plots saved to: {out_dir}")

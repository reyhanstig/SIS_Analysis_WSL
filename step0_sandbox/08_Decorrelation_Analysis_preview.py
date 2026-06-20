import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os
import sys
from pathlib import Path

# Add project root to sys.path to import scripts
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from scripts.paths import ProjectPaths

# Apply the global project style
plt.style.use(str(project_root / 'project_style.mplstyle'))

def create_synthetic_presentation_figure():
    """
    Generates a simplified, conceptual figure of the decorrelation scale calculation.
    Uses synthetic data designed purely for presentation/methods explanation to ensure
    very clean visuals without needing to load large realistic datasets.
    """
    print("Generating synthetic presentation figure...")
    # Set random seed for reproduction of the conceptual plot
    np.random.seed(42)

    # --- 1. Generate Synthetic Data ---

    # A. Background (noise) data
    n_bg = 1500
    bg_dists_sample = np.random.uniform(5, 100, n_bg)
    bg_corrs_sample = np.random.normal(0.1, 0.3, n_bg)
    bg_corrs_sample = np.clip(bg_corrs_sample, -1, 1)

    # B. Target Station Data
    n_target = 35
    target_dists = np.random.uniform(5, 100, n_target)
    
    # Make target station correlations follow a gaussian plus offset
    A_fit = 0.91
    B_fit = 0.09
    dx_param = 15.0 # spatial decay scale
    r_crit = 0.430
    decorr_dist = 11.8

    # Add the point at distance 0
    target_dists = np.append(target_dists, 0)
    target_corrs_clean = A_fit * np.exp(-(target_dists / dx_param)**2) + B_fit
    target_corrs = target_corrs_clean + np.random.normal(0, 0.12, len(target_dists))
    target_corrs[-1] = 1.0 # The x=0 point has exactly correlation 1.0
    target_corrs = np.clip(target_corrs, -1, 1)

    # --- 2. Setup Figure ---
    plt.figure(figsize=(10, 6))

    # Plot Background Points
    plt.scatter(bg_dists_sample, bg_corrs_sample, color='lightgrey', alpha=0.3, s=15, 
                label='Background Station Pairs')

    # Plot Target Station Points
    plt.scatter(target_dists, target_corrs, color='blue', alpha=0.7, s=45, 
                label='Target Station Pairs')

    # Plot Fitted Gaussian Curve
    x_line = np.linspace(0, 100, 200)
    y_line = A_fit * np.exp(-(x_line / dx_param)**2) + B_fit
    plt.plot(x_line, y_line, color='red', linewidth=3, label='Gaussian Fit Model')

    # Annotations and Lines
    # Horizontal line at r = r_crit
    plt.axhline(y=r_crit, color='green', linestyle=':', linewidth=2.5, 
                label=r'Critical Threshold ($r_{crit}$)')

    # Vertical line at the decorrelation distance
    plt.axvline(x=decorr_dist, color='green', linestyle='--', linewidth=2.5, 
                label=r'Decorrelation Scale ($L$)')
    
    # Intersection Dot
    plt.plot(decorr_dist, r_crit, 'go', markersize=10, zorder=5)

    # Asymptotic Floor B
    plt.axhline(y=B_fit, color='orange', linestyle='-.', linewidth=2.5, alpha=0.9, 
                label=r'Asymptotic Floor ($B$)')

    # --- 3. Aesthetics & Saving ---
    # Removed specific Station IDs and Water Mass specific references
    plt.title('Decorrelation Scale Calculation Model', fontsize=20, fontweight='bold', pad=15)
    plt.xlabel('Distance (km)', fontsize=18)
    plt.ylabel('Correlation Coefficient ($r$)', fontsize=18)

    plt.axhline(0, color='black', linewidth=1)
    plt.xlim(0, 100)
    plt.ylim(-0.5, 1.1)

    # Enhanced legend for slide aspect ratios
    plt.legend(loc='upper right', fontsize=12, framealpha=0.95, edgecolor='grey')
    plt.grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    
    # Save output for PPT using the ProjectPaths (points to C:\Users\reyha\Documents\SIS_Analysis_Windows\figures via symlink)
    save_dir = ProjectPaths.FIGURES_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / 'decorrelation_methods_figure.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved figure to: {save_path}")
    # plt.show() # Commented out because it blocks the terminal execution in WSL

# ===================================================================
# --- OPTION 2: REAL DATA VERSION ---
# If you prefer to plot this using your *real data* in the Jupyter Notebook,
# you can copy/paste this snippet into a notebook cell.
# ===================================================================
"""
# 1. Pick a station to test
test_station_idx = 105
if len(results_df) > 0:
    row = results_df.iloc[test_station_idx]
    station_id = row['Station_ID']
    decorr_dist = row['Decorrelation_Scale_km']
    A_fit = row['Amplitude_A']
    B_fit = row['Offset_B']
    dx_param = row['dx_param']
    r_crit = row['r_crit']
    
    # Get specific station data
    target_series = yearly_do_df.loc[station_id]
    correlations = yearly_do_df.corrwith(target_series, axis=1, drop=True)
    
    # Gather data points for this station
    plot_data = []
    for neighbor in yearly_do_df.index:
        valid_count = pd.concat([target_series, yearly_do_df.loc[neighbor]], axis=1).dropna().shape[0]
        if valid_count >= min_periods:
            if neighbor == station_id:
                plot_data.append({'dist': 0.0, 'corr': 1.0})
            else:
                d_val = dist_matrix_km.loc[station_id, neighbor]
                c_val = correlations[neighbor]
                if not np.isnan(d_val) and not np.isnan(c_val):
                    plot_data.append({'dist': d_val, 'corr': c_val})
    
    df_test = pd.DataFrame(plot_data)

    # Determine X axis limit
    x_limit = np.ceil(2 * decorr_dist) if decorr_dist > 100 else 100
    
    # Setup Figure
    plt.figure(figsize=(10, 6))
    
    # A. Plot Background
    if 'bg_dists_sample' in locals():
        plt.scatter(bg_dists_sample, bg_corrs_sample, color='lightgrey', alpha=0.3, s=15, label='Background Station Pairs')
    
    # B. Plot Target Station Data
    plt.scatter(df_test['dist'], df_test['corr'], color='blue', alpha=0.7, s=45, label='Target Station Pairs')
    
    # C. Plot Fitted Gaussian Curve with Offset
    x_line = np.linspace(0, 300, 200)
    y_line = A_fit * np.exp(-(x_line / dx_param)**2) + B_fit
    plt.plot(x_line, y_line, color='red', linewidth=3, label='Gaussian Fit Model')
    
    # D. Plot Crossing Lines
    plt.axhline(y=r_crit, color='green', linestyle=':', linewidth=2.5, label=r'Critical Threshold ($r_{crit}$)')
    
    if decorr_dist > 0:
        plt.axvline(x=decorr_dist, color='green', linestyle='--', linewidth=2.5, label=r'Decorrelation Scale ($L$)')
        plt.plot(decorr_dist, r_crit, 'go', markersize=10, zorder=5)

    # E. Asymptotic Floor B
    plt.axhline(y=B_fit, color='orange', linestyle='-.', linewidth=2.5, alpha=0.9, label=r'Asymptotic Floor ($B$)')

    # Aesthetics
    plt.title('Decorrelation Scale Calculation Model', fontsize=20, fontweight='bold', pad=15)
    plt.xlabel('Distance (km)', fontsize=18)
    plt.ylabel('Correlation Coefficient ($r$)', fontsize=18)
    plt.axhline(0, color='black', linewidth=1)
    plt.ylim(-0.5, 1.1)
    plt.xlim(0, x_limit)
    
    plt.legend(loc='upper right', fontsize=12, framealpha=0.95, edgecolor='grey')
    plt.grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    
    save_dir = ProjectPaths.FIGURES_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / 'decorrelation_methods_figure_real.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved figure to {save_path}")
    # plt.show()
"""

if __name__ == "__main__":
    create_synthetic_presentation_figure()

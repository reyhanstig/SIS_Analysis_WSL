# -*- coding: utf-8 -*-
"""
Script to analyze and plot the relationship between Decorrelation Scale and Hypoxia Frequency/Trend.
Outputs:
1. Hypoxia Frequency vs Decorrelation Scale (Scatter Plot)
2. Hypoxia Trend vs Decorrelation Scale (Bubble Chart)
"""

import sys
import os
from pathlib import Path
import shutil
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import yaml

# Add project root to sys.path
CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.paths import ProjectPaths
from utils.data_loader import load_and_process_data

# Set global project plotting style
plt.style.use(str(PROJECT_ROOT / 'project_style.mplstyle'))

# Configure output directory
OUTPUT_DIR = ProjectPaths.FIGURES_DIR / "step0_sandbox" / "64_hypoxia_frequency_vs_decorrelation_scale"

# Setup logging
log_file = CURRENT_SCRIPT.parent / "log_hypoxia_decorrelation_plot.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')

def calculate_hypoxia_frequency(df, threshold=5.0):
    """
    Calculate the hypoxia frequency per station.
    Frequency = (Years with DO < threshold) / (Total sampled years) * 100
    """
    # Total sampled years per station
    station_total_years = df.groupby('zettaicode')['year'].nunique().reset_index(name='total_sampled_years')
    
    # Years with hypoxia
    hypoxia_events = df[df['do_'] < threshold]
    station_hypoxia_years = hypoxia_events.groupby('zettaicode')['year'].nunique().reset_index(name='hypoxia_years')
    
    # Merge and calculate frequency
    hypoxia_stats = pd.merge(station_total_years, station_hypoxia_years, on='zettaicode', how='left')
    hypoxia_stats['hypoxia_years'] = hypoxia_stats['hypoxia_years'].fillna(0)
    hypoxia_stats['hypoxia_frequency'] = (hypoxia_stats['hypoxia_years'] / hypoxia_stats['total_sampled_years']) * 100
    hypoxia_stats['zettaicode'] = hypoxia_stats['zettaicode'].astype(str).str.zfill(8)
    
    return hypoxia_stats

def calculate_hypoxia_trend(df):
    """
    Calculate the linear trend (slope) of DO over time per station.
    Also calculates P_recent (proxy for recent severity or significance).
    """
    def get_trend_stats(group):
        group = group.dropna(subset=['do_', 'year'])
        if len(group['year'].unique()) < 5:
            return pd.Series({'delta': np.nan, 'p_recent': np.nan})
        
        # Aggregate mean DO per year
        yearly_mean = group.groupby('year')['do_'].mean()
        years = yearly_mean.index.values
        values = yearly_mean.values
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(years, values)
        
        # P_recent: Use frequency of recent hypoxia as a proxy, or inverse p_value.
        # Here we use 1 - p_value as a simple size scale, scaled to [0, 1]
        p_recent = max(0, 1 - p_value) if not np.isnan(p_value) else 0
        
        return pd.Series({'delta': slope, 'p_recent': p_recent})

    trends = df.groupby('zettaicode').apply(get_trend_stats, include_groups=False).reset_index()
    trends['zettaicode'] = trends['zettaicode'].astype(str).str.zfill(8)
    return trends

def main():
    # Target regions and their corresponding decorrelation file names
    target_regions = {
        'Osaka Bay': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/osaka_bay_decorrelation_scale.csv',
        'Kii Channel': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/kii_channel_decorrelation_scale.csv',
        'Harima Nada': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/harima_nada_decorrelation_scale.csv',
        'Iyo Nada': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/iyo_nada_decorrelation_scale.csv',
        'Suo Nada': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/suo_nada_decorrelation_scale.csv',
        'Bisan Seto': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/bisan_seto_decorrelation_scale.csv',
        'Bungo Channel': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/bungo_channel_decorrelation_scale.csv',
        'Bingo Nada': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/bingo_nada_decorrelation_scale.csv',
        'Hibiki Nada': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/hibiki_nada_decorrelation_scale.csv',
        'Aki Nada': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/aki_nada_decorrelation_scale.csv',
        'Hiuchi Nada': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/hiuchi_nada_decorrelation_scale.csv',
        'Hiroshima Bay': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/hiroshima_bay_decorrelation_scale.csv',
        'Tokyo Bay': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/tokyo_bay_decorrelation_scale.csv',
        'Ise Bay': 'step3_decorrelation_scale_analysis/process11_calculate_decorrelation_scale_per_bay/ise_mikawa_bay_decorrelation_scale.csv'
    }
    
    # Clean output directory
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load parameters
    with open(PROJECT_ROOT / 'params.yaml', 'r') as f:
        params = yaml.safe_load(f)
    REP_MONTH_SUMMER = params['seasonal_subsets']['representative_months']['Summer']
    
    # Load data
    logging.info("Loading merged data...")
    merged_gdf = load_and_process_data(force_reload=False)
    merged_gdf['do_'] = pd.to_numeric(merged_gdf['do_'], errors='coerce')
    
    for region, decorr_filename in target_regions.items():
        print(f"Processing region: {region}")
        logging.info(f"Processing region: {region}")
        
        decorr_file = ProjectPaths.PROCESSED_DATA_DIR / decorr_filename
        if not decorr_file.exists():
            logging.error(f"Decorrelation file not found for {region}: {decorr_file}")
            print(f"Error: {decorr_file} not found. Skipping.")
            continue
            
        dec_df = pd.read_csv(decorr_file)
        dec_df['Station_ID'] = dec_df['Station_ID'].astype(str).str.zfill(8)
        
        # Filter for the region and Summer Bottom layer
        # Tokyo Bay mostly samples in August (8) instead of July (7)
        rep_month = 8 if region == 'Tokyo Bay' else REP_MONTH_SUMMER
        
        region_col = 'watermass_name' if region in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea'] else 'division'
        
        df_region = merged_gdf[
            (merged_gdf[region_col] == region) &
            (merged_gdf['surveymont'] == rep_month) &
            (merged_gdf['saisuipoin'] == 2)
        ].copy()
        
        if df_region.empty:
            logging.warning(f"No data for {region} in Summer Bottom. Skipping.")
            print(f"No data for {region}. Skipping.")
            continue
            
        # 1. Calculate Hypoxia Frequency (DO < 5.0 mg/L)
        freq_stats = calculate_hypoxia_frequency(df_region, threshold=5.0)
        
        # 2. Calculate Hypoxia Trend
        trend_stats = calculate_hypoxia_trend(df_region)
        
        # Merge all stats
        merged_stats = freq_stats.merge(trend_stats, on='zettaicode', how='inner')
        plot_df = dec_df.merge(merged_stats, left_on='Station_ID', right_on='zettaicode', how='inner')
        
        # Filter stations with enough data (e.g., at least 10 years)
        plot_df = plot_df[plot_df['total_sampled_years'] >= 10]
        plot_df = plot_df.dropna(subset=['Decorrelation_Scale_km', 'hypoxia_frequency', 'delta'])
        
        if len(plot_df) < 3:
            logging.warning(f"Not enough data points for {region} after merging. Skipping.")
            print(f"Not enough valid stations for {region}. Skipping.")
            continue
        
        region_clean = region.replace(" ", "_")
        
        # --- Plot 1: Hypoxia Frequency vs Decorrelation Scale ---
        plt.figure(figsize=(9, 6))
        sns.scatterplot(data=plot_df, x='Decorrelation_Scale_km', y='hypoxia_frequency', alpha=0.6)
        
        # Add trendline
        corr, p_val = stats.pearsonr(plot_df['Decorrelation_Scale_km'], plot_df['hypoxia_frequency'])
        m, b = np.polyfit(plot_df['Decorrelation_Scale_km'], plot_df['hypoxia_frequency'], 1)
        x_line = np.array([plot_df['Decorrelation_Scale_km'].min(), plot_df['Decorrelation_Scale_km'].max()])
        plt.plot(x_line, m * x_line + b, color='red', linestyle='--', label=f'Trendline (r={corr:.2f}, p={p_val:.3f})')
        
        plt.title(f'Hypoxia Frequency vs Decorrelation Scale\n{region} (Summer Bottom)')
        plt.xlabel('Decorrelation Scale (km)')
        plt.ylabel('Hypoxia Frequency (% years DO < 5.0 mg/L)')
        plt.legend()
        plt.tight_layout()
        
        out_path1 = OUTPUT_DIR / f'hypoxia_frequency_vs_decorr_{region_clean}.png'
        plt.savefig(out_path1, dpi=300, bbox_inches='tight')
        plt.close()
        
        # --- Plot 2: Hypoxia Trend vs Decorrelation Scale ---
        plt.figure(figsize=(10, 7))
        
        # Determine vmax for diverging colormap
        vmax = max(abs(plot_df['delta'].min()), abs(plot_df['delta'].max()), 0.05)
        
        scatter = plt.scatter(
            plot_df['Decorrelation_Scale_km'], 
            plot_df['delta'],
            c=plot_df['delta'],
            s=plot_df['p_recent'] * 500 + 50,  # Scale size
            cmap='vlag',  # Diverging colormap (blue to red)
            vmin=-vmax, vmax=vmax,
            alpha=0.7,
            edgecolors='grey'
        )
        
        cbar = plt.colorbar(scatter)
        cbar.set_label('Trend (Worsening > 0 > Improving)')
        
        # Trendline for bubble chart
        corr_trend, p_val_trend = stats.pearsonr(plot_df['Decorrelation_Scale_km'], plot_df['delta'])
        m2, b2 = np.polyfit(plot_df['Decorrelation_Scale_km'], plot_df['delta'], 1)
        plt.plot(x_line, m2 * x_line + b2, color='darkred', linewidth=2, label=f'Linear Trend\n$R^2$={corr_trend**2:.2f}, p={p_val_trend:.3f}')
        plt.axhline(0, color='gray', linestyle='--', alpha=0.5)
        
        plt.title(f'Hypoxia Trend vs. Decorrelation Scale\n{region} (Summer Bottom)')
        plt.xlabel('Decorrelation Scale (km)')
        plt.ylabel('Hypoxia Trend (Slope)')
        plt.legend()
        plt.tight_layout()
        
        out_path2 = OUTPUT_DIR / f'hypoxia_trend_vs_decorr_hypox_{region_clean}.png'
        plt.savefig(out_path2, dpi=300, bbox_inches='tight')
        plt.close()
        
        logging.info(f"Successfully generated plots for {region}")
        print(f"Generated plots for {region}")

if __name__ == "__main__":
    main()

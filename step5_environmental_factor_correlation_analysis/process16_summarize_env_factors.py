import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import re
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Global plot settings
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))
from utils.paths import ProjectPaths

plt.style.use(str(project_root / 'project_style.mplstyle'))

# Paths to search
step5_dir = ProjectPaths.PROCESSED_DATA_DIR / "step5_environmental_factor_correlation_analysis"
step6_dir = ProjectPaths.PROCESSED_DATA_DIR / "step6_pick_up_area_location"

out_dir = ProjectPaths.FIGURES_DIR / "step6_pick_up_area_location" / "process05_summarize_env_factors"
out_dir.mkdir(parents=True, exist_ok=True)
data_out_dir = ProjectPaths.PROCESSED_DATA_DIR / "step6_pick_up_area_location" / "process05_summarize_env_factors"
data_out_dir.mkdir(parents=True, exist_ok=True)

def normalize_param_name(name):
    name = str(name).replace('_', ' ').lower().strip()
    
    # Handle acronyms that include depth
    if 'sst' in name: name = name.replace('sst', 'surface wtemp')
    if 'sbt' in name: name = name.replace('sbt', 'bottom wtemp')
    if 'sss' in name: name = name.replace('sss', 'surface salt')
    if 'sbs' in name: name = name.replace('sbs', 'bottom salt')
    
    replacements = {
        'nh4n2': 'NH4-N', 'nh4n': 'NH4-N',
        'no3n2': 'NO3-N', 'no3n': 'NO3-N',
        'no2n2': 'NO2-N', 'no2n': 'NO2-N',
        'po4p2': 'PO4-P', 'po4p': 'PO4-P',
        'din2': 'DIN', 'din': 'DIN',
        'dip2': 'DIP', 'dip': 'DIP',
        'tn2': 'TN', 'tn': 'TN',
        'tp2': 'TP', 'tp': 'TP',
        'cod2': 'COD', 'cod': 'COD',
        'doc2': 'DOC', 'doc': 'DOC',
        'chla': 'Chl-a', 'chla2': 'Chl-a',
        'salt2': 'SALT', 'salt': 'SALT',
        'wtemp': 'WTEMP', 'density': 'Density',
        'do': 'DO',
        'summer': 'Summer', 'winter': 'Winter', 'spring': 'Spring', 'autumn': 'Autumn',
        'bottom': 'Bottom', 'surface': 'Surface',
        'stratification': 'Stratification',
        'air': 'Air', 'temp': 'Temp', 'wind': 'Wind', 'speed': 'Speed',
        '1': '1', '2': '2'
    }
    
    parts = name.split()
    formatted_parts = []
    
    for p in parts:
        if p in replacements:
            formatted_parts.append(replacements[p])
        else:
            formatted_parts.append(p.capitalize())
            
    # standardize order: Depth, Season, Number (if any), Parameter
    depth = ""
    season = ""
    num = ""
    param = []
    
    for p in formatted_parts:
        if p in ["Bottom", "Surface"]:
            depth = p
        elif p in ["Summer", "Winter", "Spring", "Autumn"]:
            season = p
        elif p in ["1", "2"]:
            num = p
        else:
            param.append(p)
            
    final_name_parts = []
    if depth: final_name_parts.append(depth)
    if season: final_name_parts.append(season)
    if num: final_name_parts.append(num)
    final_name_parts.extend(param)
    
    return " ".join(final_name_parts).strip()

def get_basin_from_path(path_str):
    if "Seto_Inland_Sea" in path_str: return "Seto Inland Sea"
    if "Tokyo_Bay" in path_str: return "Tokyo Bay"
    if "Ise_Bay" in path_str or "Mikawa_Bay" in path_str or "Ise_Mikawa_Bay" in path_str: 
        return "Ise Mikawa Bay"
    return "Unknown"

def get_year_period_from_path(path_str):
    match = re.search(r'(\d{4})_(\d{4})', path_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    match = re.search(r'(\d{4})-(\d{4})', path_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return "All Years"

def main():
    permutations_data = {}

    def add_count(basin, year_period, param, is_significant, r_value=None):
        if (basin, year_period) not in permutations_data:
            permutations_data[(basin, year_period)] = {
                'significant_pos_counts': {},
                'significant_neg_counts': {},
                'total_counts': {}
            }
        
        counts = permutations_data[(basin, year_period)]
        norm_param = normalize_param_name(param)
        
        if norm_param not in counts['total_counts']:
            counts['total_counts'][norm_param] = 0
            counts['significant_pos_counts'][norm_param] = 0
            counts['significant_neg_counts'][norm_param] = 0
            
        counts['total_counts'][norm_param] += 1
        if is_significant:
            if r_value is None or r_value >= 0:
                counts['significant_pos_counts'][norm_param] += 1
            else:
                counts['significant_neg_counts'][norm_param] += 1

    # Process Step 5
    if step5_dir.exists():
        for root, _, files in os.walk(step5_dir):
            for f in files:
                if f.endswith(".csv") and ("p_values" in f):
                    path_str = os.path.join(root, f)
                    basin = get_basin_from_path(path_str)
                    if basin == "Unknown": continue
                    year_period = get_year_period_from_path(path_str)
                    
                    try:
                        df = pd.read_csv(path_str)
                        if 'Parameter' in df.columns and 'P_Value' in df.columns:
                            for _, row in df.iterrows():
                                param = row['Parameter']
                                pval = row['P_Value']
                                if pd.notna(pval):
                                    add_count(basin, year_period, param, float(pval) < 0.05)
                    except Exception as e:
                        logging.warning(f"Failed to read or process {path_str}: {e}")

    # Process Step 6
    if step6_dir.exists():
        for root, _, files in os.walk(step6_dir):
            for f in files:
                if f.endswith(".csv"):
                    path_str = os.path.join(root, f)
                    basin = get_basin_from_path(path_str)
                    if basin == "Unknown": continue
                    year_period = get_year_period_from_path(path_str)
                    
                    try:
                        df = pd.read_csv(path_str)
                        if 'Env_Parameter' in df.columns and 'p_value' in df.columns:
                            # process04 format
                            for _, row in df.iterrows():
                                param = row['Env_Parameter']
                                pval = row['p_value']
                                r_val = row.get('r_value', None)
                                if pd.notna(pval):
                                    add_count(basin, year_period, param, float(pval) < 0.05, float(r_val) if pd.notna(r_val) else None)
                        else:
                            # process01 format
                            pval_cols = [c for c in df.columns if c.endswith('_pval')]
                            for col in pval_cols:
                                param = col[:-5] # remove '_pval'
                                if param not in df.columns: continue
                                for idx, pval in df[col].items():
                                    if pd.notna(pval):
                                        r_val = df.at[idx, param]
                                        add_count(basin, year_period, param, float(pval) < 0.05, float(r_val) if pd.notna(r_val) else None)
                    except Exception as e:
                        logging.warning(f"Failed to read or process {path_str}: {e}")

    if not permutations_data:
        logging.warning("No data found in step5 or step6 directories to summarize.")
        return

    for (basin, year_period), counts in permutations_data.items():
        total_counts = counts['total_counts']
        
        results = []
        for param in total_counts:
            sig_pos = counts['significant_pos_counts'][param]
            sig_neg = counts['significant_neg_counts'][param]
            tot = total_counts[param]
            sig_total = sig_pos + sig_neg
            results.append({
                'Parameter': param,
                'Positive': sig_pos,
                'Negative': sig_neg,
                'Total_Significant': sig_total,
                'Total_Count': tot,
                'Significance_Rate': sig_total / tot if tot > 0 else 0
            })
            
        if not results:
            continue
            
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values(by='Total_Significant', ascending=False).head(20) # top 20
        
        if results_df.empty or results_df['Total_Significant'].max() == 0:
            logging.info(f"Skipping plot for {basin} ({year_period}) as there are 0 significant factors.")
            continue
            
        safe_basin = basin.replace(" ", "_")
        safe_year = year_period.replace(" ", "_")
        
        # Save CSV
        csv_out_path = data_out_dir / f"dominance_summary_{safe_basin}_{safe_year}_v3.csv"
        results_df.to_csv(csv_out_path, index=False)
        logging.info(f"Data saved to {csv_out_path}")
        
        # Plot
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Sort ascending for barh so largest is at the top
        results_df_plot = results_df.sort_values(by='Total_Significant', ascending=True)
        
        ax.barh(results_df_plot['Parameter'], results_df_plot['Positive'], color='indianred', label='Significant Positive (r > 0)')
        ax.barh(results_df_plot['Parameter'], -results_df_plot['Negative'], color='steelblue', label='Significant Negative (r < 0)')
        ax.axvline(0, color='black', linewidth=1)
        
        ax.set_title(f'Top 20 Environmental Factors - {basin} ({year_period})\n(Based on # of significant correlations)')
        ax.set_xlabel('Number of Significant Findings (p < 0.05)')
        ax.set_ylabel('Environmental Factor')
        ax.legend(loc='lower right')
        
        plt.tight_layout()
        
        out_path = out_dir / f"dominance_summary_{safe_basin}_{safe_year}_v3.png"
        plt.savefig(out_path, dpi=300)
        plt.close()
        
        logging.info(f"Plot saved to {out_path}")

if __name__ == "__main__":
    main()

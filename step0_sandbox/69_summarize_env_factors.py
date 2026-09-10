import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Paths to search
step5_dir = Path("data/processed/step5_environmental_factor_correlation_analysis")
step6_dir = Path("data/processed/step6_pick_up_area_location")

significant_counts = {}
total_counts = {}

def normalize_param_name(name):
    # Normalize common variations
    name = name.replace('_', ' ')
    name = name.lower().strip()
    
    # some manual mapping based on observed names
    mapping = {
        'bottom summer dip': 'summer dip',
        'bottom summer cod': 'summer cod',
        'bottom summer din': 'summer din',
        'bottom summer tp': 'summer tp',
        'bottom summer chl-a': 'summer chla',
        'surface summer do': 'summer do',
        'summer sst': 'summer wtemp', # assuming sea surface temp is wtemp
        'summer sbt': 'bottom wtemp', # sea bottom temp
        'surface summer dip': 'summer dip',
        'summer sbs': 'bottom salt',
        'surface summer din': 'summer din',
        'surface summer doc': 'summer doc',
        'surface summer cod': 'summer cod',
        'surface summer tn': 'summer tn',
        'bottom summer tn': 'summer tn',
        'surface summer chl-a': 'summer chla',
        'summer sss': 'surface salt',
        'surface summer tp': 'summer tp',
        'bottom summer doc': 'summer doc',
        'summer stratification': 'summer stratification',
        'winter stratification': 'winter stratification',
        'winter air temp': 'winter air temp',
        'summer wind speed': 'summer wind speed'
    }
    
    # Format nutrient and parameter names
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
        'do': 'DO'
    }
    
    if name in mapping:
        name = mapping[name]
        
    parts = name.split(' ')
    formatted_parts = []
    for p in parts:
        if p in replacements:
            formatted_parts.append(replacements[p])
        else:
            formatted_parts.append(p.capitalize())
            
    name = ' '.join(formatted_parts)
    
    return name

def add_count(param, is_significant):
    norm_param = normalize_param_name(param)
    if norm_param not in total_counts:
        total_counts[norm_param] = 0
        significant_counts[norm_param] = 0
    total_counts[norm_param] += 1
    if is_significant:
        significant_counts[norm_param] += 1

# Process Step 5
for root, _, files in os.walk(step5_dir):
    for f in files:
        if f.endswith(".csv") and ("p_values" in f):
            df = pd.read_csv(os.path.join(root, f))
            if 'Parameter' in df.columns and 'P_Value' in df.columns:
                for _, row in df.iterrows():
                    param = row['Parameter']
                    pval = row['P_Value']
                    if pd.notna(pval):
                        add_count(param, float(pval) < 0.05)

# Process Step 6
for root, _, files in os.walk(step6_dir):
    for f in files:
        if f.endswith(".csv"):
            df = pd.read_csv(os.path.join(root, f))
            if 'Env_Parameter' in df.columns and 'p_value' in df.columns:
                # process04 format
                for _, row in df.iterrows():
                    param = row['Env_Parameter']
                    pval = row['p_value']
                    if pd.notna(pval):
                        add_count(param, float(pval) < 0.05)
            else:
                # process01 format
                pval_cols = [c for c in df.columns if c.endswith('_pval')]
                for col in pval_cols:
                    param = col[:-5] # remove '_pval'
                    for pval in df[col]:
                        if pd.notna(pval):
                            add_count(param, float(pval) < 0.05)

# Calculate dominance metric (e.g. number of significant occurrences)
results = []
for param in total_counts:
    sig = significant_counts[param]
    tot = total_counts[param]
    results.append({
        'Parameter': param,
        'Significant_Count': sig,
        'Total_Count': tot,
        'Significance_Rate': sig / tot if tot > 0 else 0
    })

results_df = pd.DataFrame(results)
# Sort by significant count as primary measure of dominance
results_df = results_df.sort_values(by='Significant_Count', ascending=False).head(20) # top 20

plt.figure(figsize=(12, 8))
sns.barplot(data=results_df, x='Significant_Count', y='Parameter', palette='viridis')
plt.title('Top 20 Most Dominant Environmental Factors\n(Based on # of significant correlations in Step 5 & 6)')
plt.xlabel('Number of Significant Findings (p < 0.05)')
plt.ylabel('Environmental Factor')
plt.tight_layout()

out_path = Path("/home/reyha/SIS_Analysis_WSL/figures/step0_sandbox/69_summarize_env_factors/dominance_summary.png")
out_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out_path, dpi=300)
print(f"Plot saved to {out_path}")

print("\nTop Factors by Significant Count:")
print(results_df[['Parameter', 'Significant_Count', 'Total_Count', 'Significance_Rate']].to_string(index=False))

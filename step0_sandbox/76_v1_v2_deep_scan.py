import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path('/home/reyha/SIS_Analysis_WSL')))
from utils.data_loader import load_raw_shapefiles, get_season

print("Loading raw shapefiles (this might take a minute)...")
# Load raw data without the V2 column overwrite
raw_gdf = load_raw_shapefiles()

print("Calculating seasons...")
raw_gdf['surveymont'] = pd.to_numeric(raw_gdf['surveymont'], errors='coerce')
raw_gdf['season'] = raw_gdf['surveymont'].apply(get_season)

# Define column pairs
pairs = {
    'do_': 'do_2', 'ph': 'ph2', 'salt': 'salt2', 
    'cod': 'cod2', 'rcod': 'rcod2', 'nh4n': 'nh4n2', 
    'no2n': 'no2n2', 'no3n': 'no3n2', 'tn': 'tn2', 
    'po4p': 'po4p2', 'tp': 'tp2', 'chlorophyl': 'chloroph_1', 
    'feiochin': 'feiochin2', 'toc': 'toc2', 'doc': 'doc2'
}

results = []

print("Scanning parameter permutations...")
for v1_col, v2_col in pairs.items():
    if v1_col not in raw_gdf.columns or v2_col not in raw_gdf.columns:
        continue
        
    # Convert both to numeric
    v1_num = pd.to_numeric(raw_gdf[v1_col], errors='coerce')
    v2_num = pd.to_numeric(raw_gdf[v2_col], errors='coerce')
    
    # We want to group by basin, layer, season
    # Basin: watermass_name (or division)
    # Layer: saisuipoin (1=surface, 2=bottom)
    
    # Create a temporary dataframe for fast grouped operations
    temp_df = pd.DataFrame({
        'basin': raw_gdf['watermass_name'],
        'layer': raw_gdf['saisuipoin'],
        'season': raw_gdf['season'],
        'v1': v1_num,
        'v2': v2_num
    })
    
    # Filter out empty basin
    temp_df = temp_df.dropna(subset=['basin', 'layer', 'season'])
    
    # Group by permutations
    grouped = temp_df.groupby(['basin', 'layer', 'season'])
    
    for name, group in grouped:
        basin, layer, season = name
        
        # When both are valid and non-zero, do they match?
        both_valid_mask = group['v1'].notna() & group['v2'].notna()
        # Allow small floating point tolerance
        matches = np.isclose(group.loc[both_valid_mask, 'v1'], group.loc[both_valid_mask, 'v2'], rtol=1e-5, atol=1e-5).sum()
        both_valid_count = both_valid_mask.sum()
        
        # When v1 is NaN, is v2 == 0.0?
        v1_missing_mask = group['v1'].isna()
        v2_is_zero_when_v1_missing = (group.loc[v1_missing_mask, 'v2'] == 0.0).sum()
        v1_missing_count = v1_missing_mask.sum()
        
        # When v1 is valid, is v2 missing?
        v2_missing_when_v1_valid = group.loc[~v1_missing_mask, 'v2'].isna().sum()
        
        match_rate = (matches / both_valid_count) if both_valid_count > 0 else np.nan
        zero_fill_rate = (v2_is_zero_when_v1_missing / v1_missing_count) if v1_missing_count > 0 else np.nan
        
        results.append({
            'parameter': v1_col,
            'basin': basin,
            'layer': layer,
            'season': season,
            'v1_valid_count': group['v1'].notna().sum(),
            'v2_valid_count': group['v2'].notna().sum(),
            'both_valid_count': both_valid_count,
            'match_count': matches,
            'match_rate': match_rate,
            'v1_missing_count': v1_missing_count,
            'v2_is_zero_when_v1_missing': v2_is_zero_when_v1_missing,
            'zero_fill_rate': zero_fill_rate,
            'v2_missing_when_v1_valid': v2_missing_when_v1_valid
        })

results_df = pd.DataFrame(results)
output_path = '/home/reyha/SIS_Analysis_WSL/step0_sandbox/76_v1_v2_deep_scan_results.csv'
results_df.to_csv(output_path, index=False)
print(f"Deep scan complete. Results saved to {output_path}")

# Quick overall summary print
print("\nOverall Parameter Summary (Aggregated):")
agg_df = results_df.groupby('parameter').agg({
    'v1_valid_count': 'sum',
    'v2_valid_count': 'sum',
    'both_valid_count': 'sum',
    'match_count': 'sum',
    'v1_missing_count': 'sum',
    'v2_is_zero_when_v1_missing': 'sum'
}).reset_index()

agg_df['Overall_Match_Rate'] = (agg_df['match_count'] / agg_df['both_valid_count']).apply(lambda x: f"{x*100:.2f}%")
agg_df['Zero_Fill_Rate'] = (agg_df['v2_is_zero_when_v1_missing'] / agg_df['v1_missing_count']).apply(lambda x: f"{x*100:.2f}%")

print(agg_df[['parameter', 'v1_valid_count', 'v2_valid_count', 'Overall_Match_Rate', 'Zero_Fill_Rate']])

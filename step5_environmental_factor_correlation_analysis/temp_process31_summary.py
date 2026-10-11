import argparse
import sys
from pathlib import Path
import pandas as pd
import numpy as np

CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent))
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))

# Import functions from the original script
from process31_correlation_distribution import (
    load_correlation_seasons, build_long_table, count_significant
)
from utils.paths import ProjectPaths

def main():
    parser = argparse.ArgumentParser(description="Output text summary of correlations instead of figures")
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    parser.add_argument('--data_type', required=True, choices=['env', 'nutr'])
    args = parser.parse_args()

    target_region = args.target_region
    season = args.season
    layer = args.layer
    data_type = args.data_type
    
    # Load PCA correlations
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    pc1_path = subset_dir / f'pca_{data_type}_corr_pc1.csv'
    pc2_path = subset_dir / f'pca_{data_type}_corr_pc2.csv'
    
    if not pc1_path.exists() or not pc2_path.exists():
        print(f"No data found for {target_region} {data_type}")
        return
        
    corr_df_pc1 = pd.read_csv(pc1_path, dtype={'zettaicode': str}).set_index('zettaicode')
    corr_df_pc2 = pd.read_csv(pc2_path, dtype={'zettaicode': str}).set_index('zettaicode')
    
    # Filter by region
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE, columns=['zettaicode', 'watermass_name'])
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    if target_region:
        valid_stations = merged_df[merged_df['watermass_name'] == target_region]['zettaicode'].unique()
        corr_df_pc1 = corr_df_pc1[corr_df_pc1.index.isin(valid_stations)]
        corr_df_pc2 = corr_df_pc2[corr_df_pc2.index.isin(valid_stations)]

    seasons = load_correlation_seasons()
    long_tables = {
        'PC1': build_long_table(corr_df_pc1, seasons),
        'PC2': build_long_table(corr_df_pc2, seasons),
    }

    print(f"=== SUMMARY FOR {target_region} | Data: {data_type} | PCA subset: {season} {layer} ===")
    
    for s in [season]: # Just focus on the primary season matching the PCA subset for brevity
        print(f"\nParameter Season: {s}")
        for pc in ['PC1', 'PC2']:
            df = long_tables[pc]
            df_s = df[df['Param_Season'] == s].copy()
            if df_s.empty:
                continue
                
            medians = df_s.groupby('Parameter')['Pearson_r'].median()
            counts = count_significant(df_s)
            
            print(f"\n[{pc} Results]")
            print(f"{'Parameter':<20} | {'Median r':<10} | {'Sig Pos (>0)':<15} | {'Sig Neg (<0)':<15}")
            print("-" * 68)
            
            # Sort by number of negative significant stations + positive significant stations descending
            total_sig = {}
            for param in medians.index:
                pos = int(counts.loc[(param, s), 'Positive']) if not counts.empty and (param, s) in counts.index else 0
                neg = int(counts.loc[(param, s), 'Negative']) if not counts.empty and (param, s) in counts.index else 0
                total_sig[param] = pos + neg
                
            sorted_params = sorted(medians.index, key=lambda x: total_sig[x], reverse=True)

            for param in sorted_params:
                med = medians[param]
                pos = int(counts.loc[(param, s), 'Positive']) if not counts.empty and (param, s) in counts.index else 0
                neg = int(counts.loc[(param, s), 'Negative']) if not counts.empty and (param, s) in counts.index else 0
                print(f"{param:<20} | {med:>10.3f} | {pos:>15} | {neg:>15}")
            print()

if __name__ == '__main__':
    main()

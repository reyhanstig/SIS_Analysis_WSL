import pandas as pd
import numpy as np

target_region = "Tokyo Bay"
pc1_path = "/home/reyha/SIS_Analysis_WSL/data/processed/seasonal/summer_bottom/pca_env_corr_pc1.csv"
merged_path = "/home/reyha/SIS_Analysis_WSL/data/processed/merged_gdf.feather"

corr_df_pc1 = pd.read_csv(pc1_path, dtype={'zettaicode': str}).set_index('zettaicode')
merged_df = pd.read_feather(merged_path, columns=['zettaicode', 'watermass_name'])
merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
valid_stations = merged_df[merged_df['watermass_name'] == target_region]['zettaicode'].unique()
corr_df_pc1 = corr_df_pc1[corr_df_pc1.index.isin(valid_stations)]

for col in ['Summer_1_WTEMP', 'Summer_2_WTEMP']:
    print(f"\n--- {col} ---")
    if col in corr_df_pc1.columns:
        pval_col = col + '_pval'
        sig = corr_df_pc1[corr_df_pc1[pval_col] < 0.05]
        print("Significant stations:", len(sig))
        print("Positive:", len(sig[sig[col] > 0]))
        print("Negative:", len(sig[sig[col] < 0]))
    else:
        print(f"{col} not found")


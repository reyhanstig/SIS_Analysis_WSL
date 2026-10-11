import pandas as pd
import numpy as np

DEFAULT_SEASONS = ['Spring', 'Summer', 'Autumn', 'Winter']
LAYER_NAMES = {'1': 'Surface', '2': 'Bottom'}

def parse_param_column(col, seasons):
    parts = col.split('_')
    if parts[0] not in seasons or len(parts) < 2:
        return 'Other', col.replace('_', ' ')
    param_season = parts[0]
    if parts[1] in LAYER_NAMES and len(parts) >= 3:
        label = '_'.join(parts[2:])
        return param_season, f"{LAYER_NAMES[parts[1]]} {label}"
    return param_season, '_'.join(parts[1:]).replace('_', ' ')

target_region = "Tokyo Bay"
pc1_path = "/home/reyha/SIS_Analysis_WSL/data/processed/seasonal/summer_bottom/pca_env_corr_pc1.csv"
merged_path = "/home/reyha/SIS_Analysis_WSL/data/processed/merged_gdf.feather"

corr_df = pd.read_csv(pc1_path, dtype={'zettaicode': str}).set_index('zettaicode')
merged_df = pd.read_feather(merged_path, columns=['zettaicode', 'watermass_name'])
merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
valid_stations = merged_df[merged_df['watermass_name'] == target_region]['zettaicode'].unique()
corr_df = corr_df[corr_df.index.isin(valid_stations)]

r_cols = [c for c in corr_df.columns if not c.endswith('_pval') and not c.endswith('_n')]
records = []
for col in r_cols:
    param_season, group = parse_param_column(col, DEFAULT_SEASONS)
    pval_col = f"{col}_pval"
    pvals = corr_df[pval_col] if pval_col in corr_df.columns else pd.Series(np.nan, index=corr_df.index)
    records.append(pd.DataFrame({
        'zettaicode': corr_df.index,
        'Column': col,
        'Param_Season': param_season,
        'Parameter': group,
        'Pearson_r': corr_df[col].values,
        'P_Value': pvals.values,
    }))

long_df = pd.concat(records, ignore_index=True)

sig = long_df.dropna(subset=['Pearson_r', 'P_Value'])
sig = sig[sig['P_Value'] < 0.05]
counts = sig.assign(
    Positive=(sig['Pearson_r'] > 0).astype(int),
    Negative=(sig['Pearson_r'] < 0).astype(int)
).groupby(['Parameter', 'Param_Season'])[['Positive', 'Negative']].sum()

print(counts)

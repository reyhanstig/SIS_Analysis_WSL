import pandas as pd
import numpy as np
import warnings
from scipy.stats import pearsonr
import sys
from pathlib import Path

# Add project root to sys.path to import scripts.paths
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from scripts.paths import ProjectPaths

warnings.filterwarnings('ignore')

def get_time_series_matrix(df, param, season_filter, saisuipoin=None):
    mask = df['season'] == season_filter
    if saisuipoin is not None:
        mask &= df['saisuipoin'] == saisuipoin
    
    subset = df.loc[mask, ['surveyyear', 'zettaicode', param]].copy()
    subset[param] = pd.to_numeric(subset[param], errors='coerce')
    
    matrix = subset.groupby(['surveyyear', 'zettaicode'])[param].mean().unstack()
    matrix.index = matrix.index.astype(int)
    matrix.index.name = 'year'
    
    return matrix

def calculate_station_correlations(pc_series, env_matrices, param_names, min_years=5):
    pc_series = pc_series.copy()
    pc_series.index = pc_series.index.astype(int)
    
    all_stations = set()
    for mat in env_matrices:
        all_stations.update(mat.columns)
    all_stations = sorted(all_stations)
    
    corr_records = []
    
    for stn in all_stations:
        row_corr = {'zettaicode': stn}
        row_pval = {'zettaicode': stn}
        row_n = {'zettaicode': stn}
        
        for mat, pname in zip(env_matrices, param_names):
            if stn not in mat.columns:
                row_corr[pname] = np.nan
                row_pval[pname + '_pval'] = np.nan
                row_n[pname + '_n'] = 0
                continue
            
            env_series = mat[stn].copy()
            env_series.index = env_series.index.astype(int)
            
            common_years = pc_series.index.intersection(env_series.index)
            s_pc = pc_series.loc[common_years]
            s_env = env_series.loc[common_years]
            
            valid = s_pc.notna() & s_env.notna()
            n = valid.sum()
            
            if n >= min_years:
                r, p = pearsonr(s_pc[valid], s_env[valid])
                row_corr[pname] = r
                row_pval[pname + '_pval'] = p
                row_n[pname + '_n'] = n
            else:
                row_corr[pname] = np.nan
                row_pval[pname + '_pval'] = np.nan
                row_n[pname + '_n'] = n
        
        corr_records.append({**row_corr, **row_pval, **row_n})
    
    result = pd.DataFrame(corr_records).set_index('zettaicode')
    return result

def main():
    season = 'Summer'
    layer = 'bottom'
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    pca_scores_path = subset_dir / 'pca_scores.csv'
    
    print("Loading data...")
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    pca_scores = pd.read_csv(pca_scores_path, index_col=0)
    pca_scores.index = pca_scores.index.astype(int)
    
    print("Preparing nutrients...")
    merged_df['din2'] = merged_df['nh4n2'].fillna(0) + merged_df['no2n2'].fillna(0) + merged_df['no3n2'].fillna(0)
    merged_df['dip2'] = merged_df['po4p2']
    
    print("Building time series matrices...")
    nutrients = ['cod2', 'doc2', 'tn2', 'tp2', 'din2', 'dip2', 'nh4n2', 'no2n2', 'no3n2', 'po4p2']
    env_matrices = []
    param_names = []
    
    for nutr in nutrients:
        # Surface (saisuipoin=1)
        mat_s = get_time_series_matrix(merged_df, nutr, 'Summer', saisuipoin=1)
        env_matrices.append(mat_s)
        param_names.append(f'Summer_1_{nutr.upper()}')
        
        # Bottom (saisuipoin=2)
        mat_b = get_time_series_matrix(merged_df, nutr, 'Summer', saisuipoin=2)
        env_matrices.append(mat_b)
        param_names.append(f'Summer_2_{nutr.upper()}')
        
    print("Calculating correlations...")
    corr_df_pc1 = calculate_station_correlations(pca_scores['PC1'], env_matrices, param_names)
    corr_df_pc2 = calculate_station_correlations(pca_scores['PC2'], env_matrices, param_names)
    
    out_pc1 = subset_dir / 'pca_nutr_corr_pc1.csv'
    out_pc2 = subset_dir / 'pca_nutr_corr_pc2.csv'
    
    corr_df_pc1.to_csv(out_pc1)
    corr_df_pc2.to_csv(out_pc2)
    
    print(f"Saved {out_pc1}")
    print(f"Saved {out_pc2}")
    print("Done.")

if __name__ == '__main__':
    main()

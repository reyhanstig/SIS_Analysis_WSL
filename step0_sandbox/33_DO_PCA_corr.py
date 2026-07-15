import pandas as pd
import numpy as np
import gsw
from scipy.stats import pearsonr
import sys
from pathlib import Path
import warnings

# Add project root to sys.path to import scripts.paths
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths

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

def compute_density_matrix(temp_matrix, salt_matrix, station_coords):
    density_matrix = pd.DataFrame(index=temp_matrix.index, columns=temp_matrix.columns, dtype=float)
    common_stations = temp_matrix.columns.intersection(salt_matrix.columns).intersection(station_coords.index)
    
    for stn in common_stations:
        lat = station_coords.loc[stn, 'latitude']
        lon = station_coords.loc[stn, 'longitude']
        
        t = temp_matrix[stn]
        s = salt_matrix[stn]
        
        valid = t.notna() & s.notna()
        if valid.sum() == 0:
            continue
        
        SA = gsw.SA_from_SP(s[valid], 0, lon, lat)
        CT = gsw.CT_from_t(SA, t[valid], 0)
        sigma0 = gsw.sigma0(SA, CT)
        
        density_matrix.loc[valid, stn] = sigma0.values
    
    density_matrix.index.name = 'year'
    return density_matrix.astype(float)

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
    
    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    
    print("Building time series matrices...")
    wtemp_1_matrix = get_time_series_matrix(merged_df, 'wtemp', 'Summer', saisuipoin=1)
    wtemp_2_matrix = get_time_series_matrix(merged_df, 'wtemp', 'Summer', saisuipoin=2)
    salt2_1_matrix = get_time_series_matrix(merged_df, 'salt2', 'Summer', saisuipoin=1)
    salt2_2_matrix = get_time_series_matrix(merged_df, 'salt2', 'Summer', saisuipoin=2)
    wind_matrix = get_time_series_matrix(merged_df, 'fusoku', 'Summer')
    air_t_matrix = get_time_series_matrix(merged_df, 'temp', 'Winter')
    spring_chla_1_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Spring', saisuipoin=1)
    spring_chla_2_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Spring', saisuipoin=2)
    chla_1_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Summer', saisuipoin=1)
    chla_2_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Summer', saisuipoin=2)
    
    print("Computing density matrices...")
    station_coords = stations[['latitude', 'longitude']]
    density_1_matrix = compute_density_matrix(wtemp_1_matrix, salt2_1_matrix, station_coords)
    density_2_matrix = compute_density_matrix(wtemp_2_matrix, salt2_2_matrix, station_coords)
    
    surface_depth_matrix = get_time_series_matrix(merged_df, 'saisuidept', 'Summer', saisuipoin=1)
    bottom_depth_matrix = get_time_series_matrix(merged_df, 'saisuidept', 'Summer', saisuipoin=2)
    
    depth_diff_matrix = bottom_depth_matrix - surface_depth_matrix
    depth_diff_matrix = depth_diff_matrix.replace(0, np.nan)
    stratification_matrix = (density_2_matrix - density_1_matrix) / depth_diff_matrix

    print("Computing Winter density matrices...")
    wtemp_1_matrix_w = get_time_series_matrix(merged_df, 'wtemp', 'Winter', saisuipoin=1)
    wtemp_2_matrix_w = get_time_series_matrix(merged_df, 'wtemp', 'Winter', saisuipoin=2)
    salt2_1_matrix_w = get_time_series_matrix(merged_df, 'salt2', 'Winter', saisuipoin=1)
    salt2_2_matrix_w = get_time_series_matrix(merged_df, 'salt2', 'Winter', saisuipoin=2)
    
    density_1_matrix_w = compute_density_matrix(wtemp_1_matrix_w, salt2_1_matrix_w, station_coords)
    density_2_matrix_w = compute_density_matrix(wtemp_2_matrix_w, salt2_2_matrix_w, station_coords)
    
    surface_depth_matrix_w = get_time_series_matrix(merged_df, 'saisuidept', 'Winter', saisuipoin=1)
    bottom_depth_matrix_w = get_time_series_matrix(merged_df, 'saisuidept', 'Winter', saisuipoin=2)
    
    depth_diff_matrix_w = bottom_depth_matrix_w - surface_depth_matrix_w
    depth_diff_matrix_w = depth_diff_matrix_w.replace(0, np.nan)
    winter_stratification_matrix = (density_2_matrix_w - density_1_matrix_w) / depth_diff_matrix_w
    
    env_matrices = [
        wtemp_1_matrix, wtemp_2_matrix, salt2_1_matrix, salt2_2_matrix,
        density_1_matrix, density_2_matrix, stratification_matrix, winter_stratification_matrix,
        wind_matrix, air_t_matrix, spring_chla_1_matrix, spring_chla_2_matrix,
        chla_1_matrix, chla_2_matrix
    ]
    param_names = [
        'Summer_1_WTEMP', 'Summer_2_WTEMP', 'Summer_1_SALT2', 'Summer_2_SALT2',
        'Summer_1_DENSITY', 'Summer_2_DENSITY', 'Summer_Stratification', 'Winter_Stratification',
        'Summer_Wind_Speed', 'Winter_Air_Temp', 'Spring_1_CHLA', 'Spring_2_CHLA',
        'Summer_1_CHLA', 'Summer_2_CHLA'
    ]
    
    print("Calculating correlations...")
    corr_df_pc1 = calculate_station_correlations(pca_scores['PC1'], env_matrices, param_names)
    corr_df_pc2 = calculate_station_correlations(pca_scores['PC2'], env_matrices, param_names)
    
    out_pc1 = subset_dir / 'pca_env_corr_pc1.csv'
    out_pc2 = subset_dir / 'pca_env_corr_pc2.csv'
    
    corr_df_pc1.to_csv(out_pc1)
    corr_df_pc2.to_csv(out_pc2)
    
    print(f"Saved {out_pc1}")
    print(f"Saved {out_pc2}")
    print("Done.")

if __name__ == '__main__':
    main()

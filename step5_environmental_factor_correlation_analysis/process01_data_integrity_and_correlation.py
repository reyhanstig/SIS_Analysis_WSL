import argparse
import pandas as pd
import numpy as np
import gsw
from scipy.stats import pearsonr
import sys
import logging
from pathlib import Path
import warnings

# --- BOILERPLATE INJECTED BY AGENT ---
CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')
# -------------------------------------

project_root = CURRENT_SCRIPT.parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from utils.data_loader import load_and_process_data

warnings.filterwarnings('ignore')

def get_time_series_matrix(df, param, season_filter, saisuipoin=None):
    mask = df['season'] == season_filter
    if saisuipoin is not None:
        mask &= df['saisuipoin'] == saisuipoin
    
    subset = df.loc[mask, ['surveyyear', 'zettaicode', param]].copy()
    subset[param] = pd.to_numeric(subset[param], errors='coerce')
    
    # CUT OFF METHOD: Misplaced 0 data check.
    # Nutrients and most environmental parameters cannot be exactly 0 unless it's missing/LOD.
    if param not in ['temp', 'fusoku']:
        subset[param] = subset[param].replace(0.0, np.nan)
        
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

def calculate_station_correlations(pc_series, env_matrices, param_names, min_years=15):
    pc_series = pc_series.copy()
    pc_series.index = pc_series.index.astype(int)
    
    all_stations = set()
    for mat in env_matrices:
        all_stations.update(mat.columns)
    all_stations = sorted(list(all_stations))
    
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
            
            # CUT OFF METHOD: Require at least 'min_years' of valid (non-zero/non-NaN) data
            if n >= min_years:
                if s_pc.loc[valid].std() == 0 or s_env.loc[valid].std() == 0:
                    r, p = np.nan, np.nan
                else:
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    args = parser.parse_args()
    
    season = args.season
    layer = args.layer
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    pca_scores_path = subset_dir / 'pca_scores.csv'
    
    if not pca_scores_path.exists():
        logging.error(f"PCA scores not found at {pca_scores_path}")
        return
        
    logging.info(f"Running data integrity check and correlation for {season} {layer}")
    
    merged_df = load_and_process_data(force_reload=False)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    pca_scores = pd.read_csv(pca_scores_path, index_col=0)
    pca_scores.index = pca_scores.index.astype(int)
    
    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    
    # Generate integrity report
    integrity_records = []
    v1_columns = ['wtemp', 'salt', 'chlorophyl', 'temp', 'fusoku', 'doc', 'cod', 'tn', 'tp', 'din', 'dip', 'nh4n', 'no2n', 'no3n', 'po4p']
    
    # Compute din/dip if missing (using V1 columns)
    if 'din' not in merged_df.columns:
        merged_df['din'] = pd.to_numeric(merged_df['nh4n'], errors='coerce').fillna(0) + \
                           pd.to_numeric(merged_df['no2n'], errors='coerce').fillna(0) + \
                           pd.to_numeric(merged_df['no3n'], errors='coerce').fillna(0)
        # If all three were NaN, then din should be NaN
        all_nan = merged_df['nh4n'].isna() & merged_df['no2n'].isna() & merged_df['no3n'].isna()
        merged_df.loc[all_nan, 'din'] = np.nan
        
    if 'dip' not in merged_df.columns:
        merged_df['dip'] = merged_df['po4p']

    for param in v1_columns:
        if param not in merged_df.columns:
            continue
        series = pd.to_numeric(merged_df[param], errors='coerce')
        if param not in ['temp', 'fusoku']:
            series = series.replace(0.0, np.nan)
        
        valid_count = series.notna().sum()
        missing_count = series.isna().sum()
        total_count = len(series)
        integrity_records.append({
            'Parameter': param,
            'Valid_Count': valid_count,
            'Missing_Count': missing_count,
            'Missing_Percentage': round((missing_count / total_count) * 100, 2)
        })
        
    integrity_df = pd.DataFrame(integrity_records)
    integrity_df.to_csv(PROCESSED_DATA_DIR / f'data_integrity_report_{season}_{layer}.csv', index=False)
    logging.info(f"Saved integrity report to {PROCESSED_DATA_DIR / f'data_integrity_report_{season}_{layer}.csv'}")

    logging.info("Building Environmental time series matrices (V1 columns)...")
    wtemp_1_matrix = get_time_series_matrix(merged_df, 'wtemp', season, saisuipoin=1)
    wtemp_2_matrix = get_time_series_matrix(merged_df, 'wtemp', season, saisuipoin=2)
    salt_1_matrix = get_time_series_matrix(merged_df, 'salt', season, saisuipoin=1)
    salt_2_matrix = get_time_series_matrix(merged_df, 'salt', season, saisuipoin=2)
    wind_matrix = get_time_series_matrix(merged_df, 'fusoku', season)
    air_t_matrix = get_time_series_matrix(merged_df, 'temp', 'Winter')
    spring_chla_1_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Spring', saisuipoin=1)
    spring_chla_2_matrix = get_time_series_matrix(merged_df, 'chlorophyl', 'Spring', saisuipoin=2)
    chla_1_matrix = get_time_series_matrix(merged_df, 'chlorophyl', season, saisuipoin=1)
    chla_2_matrix = get_time_series_matrix(merged_df, 'chlorophyl', season, saisuipoin=2)
    
    station_coords = stations[['latitude', 'longitude']]
    density_1_matrix = compute_density_matrix(wtemp_1_matrix, salt_1_matrix, station_coords)
    density_2_matrix = compute_density_matrix(wtemp_2_matrix, salt_2_matrix, station_coords)
    
    surface_depth_matrix = get_time_series_matrix(merged_df, 'saisuidept', season, saisuipoin=1)
    bottom_depth_matrix = get_time_series_matrix(merged_df, 'saisuidept', season, saisuipoin=2)
    
    depth_diff_matrix = bottom_depth_matrix - surface_depth_matrix
    depth_diff_matrix = depth_diff_matrix.replace(0, np.nan)
    stratification_matrix = (density_2_matrix - density_1_matrix) / depth_diff_matrix

    wtemp_1_matrix_w = get_time_series_matrix(merged_df, 'wtemp', 'Winter', saisuipoin=1)
    wtemp_2_matrix_w = get_time_series_matrix(merged_df, 'wtemp', 'Winter', saisuipoin=2)
    salt_1_matrix_w = get_time_series_matrix(merged_df, 'salt', 'Winter', saisuipoin=1)
    salt_2_matrix_w = get_time_series_matrix(merged_df, 'salt', 'Winter', saisuipoin=2)
    
    density_1_matrix_w = compute_density_matrix(wtemp_1_matrix_w, salt_1_matrix_w, station_coords)
    density_2_matrix_w = compute_density_matrix(wtemp_2_matrix_w, salt_2_matrix_w, station_coords)
    
    surface_depth_matrix_w = get_time_series_matrix(merged_df, 'saisuidept', 'Winter', saisuipoin=1)
    bottom_depth_matrix_w = get_time_series_matrix(merged_df, 'saisuidept', 'Winter', saisuipoin=2)
    
    depth_diff_matrix_w = bottom_depth_matrix_w - surface_depth_matrix_w
    depth_diff_matrix_w = depth_diff_matrix_w.replace(0, np.nan)
    winter_stratification_matrix = (density_2_matrix_w - density_1_matrix_w) / depth_diff_matrix_w
    
    env_matrices = [
        wtemp_1_matrix, wtemp_2_matrix, salt_1_matrix, salt_2_matrix,
        density_1_matrix, density_2_matrix, stratification_matrix, winter_stratification_matrix,
        wind_matrix, air_t_matrix, spring_chla_1_matrix, spring_chla_2_matrix,
        chla_1_matrix, chla_2_matrix
    ]
    env_names = [
        f'{season}_1_WTEMP', f'{season}_2_WTEMP', f'{season}_1_SALT', f'{season}_2_SALT',
        f'{season}_1_DENSITY', f'{season}_2_DENSITY', f'{season}_Stratification', 'Winter_Stratification',
        f'{season}_Wind_Speed', 'Winter_Air_Temp', 'Spring_1_CHLA', 'Spring_2_CHLA',
        f'{season}_1_CHLA', f'{season}_2_CHLA'
    ]
    
    logging.info("Calculating Environmental correlations...")
    # Get min_periods from params.yaml if available, else 15
    min_periods = 15
    param_file = project_root / 'params.yaml'
    if param_file.exists():
        import yaml
        with open(param_file, 'r') as f:
            yaml_params = yaml.safe_load(f)
            if 'min_periods' in yaml_params:
                min_periods = int(yaml_params['min_periods'])

    corr_env_pc1 = calculate_station_correlations(pca_scores['PC1'], env_matrices, env_names, min_years=min_periods)
    corr_env_pc2 = calculate_station_correlations(pca_scores['PC2'], env_matrices, env_names, min_years=min_periods)
    
    corr_env_pc1.to_csv(subset_dir / 'pca_env_corr_pc1.csv')
    corr_env_pc2.to_csv(subset_dir / 'pca_env_corr_pc2.csv')
    
    logging.info("Building Nutrient time series matrices (V1 columns)...")
    nutrients = ['cod', 'doc', 'tn', 'tp', 'din', 'dip', 'nh4n', 'no2n', 'no3n', 'po4p']
    nutr_matrices = []
    nutr_names = []
    
    for nutr in nutrients:
        mat_s = get_time_series_matrix(merged_df, nutr, season, saisuipoin=1)
        nutr_matrices.append(mat_s)
        nutr_names.append(f'{season}_1_{nutr.upper()}')
        
        mat_b = get_time_series_matrix(merged_df, nutr, season, saisuipoin=2)
        nutr_matrices.append(mat_b)
        nutr_names.append(f'{season}_2_{nutr.upper()}')
        
    logging.info("Calculating Nutrient correlations...")
    corr_nutr_pc1 = calculate_station_correlations(pca_scores['PC1'], nutr_matrices, nutr_names, min_years=min_periods)
    corr_nutr_pc2 = calculate_station_correlations(pca_scores['PC2'], nutr_matrices, nutr_names, min_years=min_periods)
    
    corr_nutr_pc1.to_csv(subset_dir / 'pca_nutr_corr_pc1.csv')
    corr_nutr_pc2.to_csv(subset_dir / 'pca_nutr_corr_pc2.csv')
    
    logging.info("Data integrity check and correlation finished successfully.")

if __name__ == '__main__':
    main()

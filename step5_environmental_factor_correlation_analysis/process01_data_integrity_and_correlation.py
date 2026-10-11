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

LAYER_CODES = [1, 2]  # saisuipoin: 1 = surface, 2 = bottom


def check_file_exists(path):
    """Log a warning and exit cleanly if a required input file is missing."""
    if not Path(path).exists():
        logging.warning(f"Required input file not found: {path}. Skipping.")
        sys.exit(0)


def load_step_parameters():
    """Load step5_parameter.csv into a {parameter_name: value} dictionary."""
    param_file = CURRENT_SCRIPT.parent / 'step5_parameter.csv'
    check_file_exists(param_file)
    df_p = pd.read_csv(param_file)
    return dict(zip(df_p['parameter_name'], df_p['value']))

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

class MatrixBuilder:
    """Build (and cache) year x station matrices for raw and derived parameters.

    Caching avoids recomputing shared inputs, e.g. wtemp/salt are reused by both
    the density and the stratification matrices of the same season.
    """

    def __init__(self, merged_df, station_coords):
        self.merged_df = merged_df
        self.station_coords = station_coords
        self._cache = {}

    def raw(self, param, season, layer_code=None):
        key = ('raw', param, season, layer_code)
        if key not in self._cache:
            self._cache[key] = get_time_series_matrix(self.merged_df, param, season, saisuipoin=layer_code)
        return self._cache[key]

    def density(self, season, layer_code):
        key = ('density', season, layer_code)
        if key not in self._cache:
            self._cache[key] = compute_density_matrix(
                self.raw('wtemp', season, layer_code),
                self.raw('salt', season, layer_code),
                self.station_coords
            )
        return self._cache[key]

    def stratification(self, season):
        key = ('stratification', season)
        if key not in self._cache:
            depth_diff = self.raw('saisuidept', season, 2) - self.raw('saisuidept', season, 1)
            depth_diff = depth_diff.replace(0, np.nan)
            self._cache[key] = (self.density(season, 2) - self.density(season, 1)) / depth_diff
        return self._cache[key]

    def build(self, source_col, derivation, season, layer_code):
        if derivation == 'density':
            return self.density(season, layer_code)
        if derivation == 'stratification':
            return self.stratification(season)
        return self.raw(source_col, season, layer_code)


def build_permutation_matrices(builder, corr_params_df, data_type, corr_seasons):
    """Expand every parameter of a data type over all correlation seasons and layers.

    Naming follows the existing convention:
        layered parameters   -> '{Season}_{layer}_{LABEL}'  (e.g. 'Winter_2_WTEMP')
        layerless parameters -> '{Season}_{LABEL}'          (e.g. 'Spring_Stratification')
    Order: parameter -> layer -> season, so all seasons of one variable are adjacent.
    """
    matrices, names = [], []
    subset = corr_params_df[corr_params_df['data_type'] == data_type]
    for _, row in subset.iterrows():
        layered = str(row['layered']).strip().lower() == 'true'
        layer_list = LAYER_CODES if layered else [None]
        for layer_code in layer_list:
            for corr_season in corr_seasons:
                name = f"{corr_season}_{layer_code}_{row['label']}" if layered else f"{corr_season}_{row['label']}"
                matrices.append(builder.build(row['source_col'], row['derivation'], corr_season, layer_code))
                names.append(name)
    return matrices, names


def calculate_station_correlations(pc_series, env_matrices, param_names, min_years=15):
    pc_series = pc_series.copy()
    pc_series.index = pc_series.index.astype(int)
    
    all_stations = set()
    for mat in env_matrices:
        all_stations.update(mat.columns)
    all_stations = sorted(list(all_stations))
    
    # Align every matrix to the PC years once (equivalent to the per-station year intersection)
    aligned_matrices = []
    for mat in env_matrices:
        mat = mat.copy()
        mat.index = mat.index.astype(int)
        aligned_matrices.append(mat.reindex(pc_series.index))
    
    corr_records = []
    
    for stn in all_stations:
        row_corr = {'zettaicode': stn}
        row_pval = {'zettaicode': stn}
        row_n = {'zettaicode': stn}
        
        for mat, pname in zip(aligned_matrices, param_names):
            if stn not in mat.columns:
                row_corr[pname] = np.nan
                row_pval[pname + '_pval'] = np.nan
                row_n[pname + '_n'] = 0
                continue
            
            s_pc = pc_series
            s_env = mat[stn]
            
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
    
    # Parameter permutations: every parameter x correlation season x depth layer
    step_params = load_step_parameters()
    corr_seasons = [s.strip() for s in str(step_params.get('correlation_seasons', 'Spring, Summer, Autumn, Winter')).split(',')]
    corr_params_file = CURRENT_SCRIPT.parent / str(step_params.get('correlation_params_file', 'step5_correlation_parameters.csv'))
    check_file_exists(corr_params_file)
    corr_params_df = pd.read_csv(corr_params_file)
        
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

    station_coords = stations[['latitude', 'longitude']]
    builder = MatrixBuilder(merged_df, station_coords)
    
    logging.info(f"Building Environmental time series matrices for seasons {corr_seasons} and both layers...")
    env_matrices, env_names = build_permutation_matrices(builder, corr_params_df, 'env', corr_seasons)
    logging.info(f"Built {len(env_names)} environmental parameter permutations.")
    
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
    
    logging.info(f"Building Nutrient time series matrices for seasons {corr_seasons} and both layers...")
    nutr_matrices, nutr_names = build_permutation_matrices(builder, corr_params_df, 'nutr', corr_seasons)
    logging.info(f"Built {len(nutr_names)} nutrient parameter permutations.")
        
    logging.info("Calculating Nutrient correlations...")
    corr_nutr_pc1 = calculate_station_correlations(pca_scores['PC1'], nutr_matrices, nutr_names, min_years=min_periods)
    corr_nutr_pc2 = calculate_station_correlations(pca_scores['PC2'], nutr_matrices, nutr_names, min_years=min_periods)
    
    corr_nutr_pc1.to_csv(subset_dir / 'pca_nutr_corr_pc1.csv')
    corr_nutr_pc2.to_csv(subset_dir / 'pca_nutr_corr_pc2.csv')
    
    logging.info("Data integrity check and correlation finished successfully.")

if __name__ == '__main__':
    main()

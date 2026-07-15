import os
import sys
import logging
from pathlib import Path
import subprocess
import pandas as pd
import shutil

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def run_script(step_dir, env, script_name, *args):
    script_path = step_dir / script_name
    cmd = [sys.executable, str(script_path)] + list(args)
    logging.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(step_dir), env=env)
    return result.returncode

def main():
    step_dir = Path(__file__).parent
    project_root_path = step_dir.parent
    
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{project_root_path}{os.pathsep}{env.get('PYTHONPATH', '')}"
    
    # 1. Get dynamic params
    param_file = step_dir / 'step5_parameter.csv'
    params = {}
    if param_file.exists():
        df_p = pd.read_csv(param_file)
        for _, row in df_p.iterrows():
            params[row['parameter_name']] = row['value']
            
    season = params.get('season', 'Summer')
    layer = params.get('layer', 'bottom')
    target_regions_str = params.get('target_region', 'Seto Inland Sea')
    target_regions = [r.strip() for r in target_regions_str.split(',')]
    
    if str(project_root_path) not in sys.path:
        sys.path.insert(0, str(project_root_path))
    from utils.paths import ProjectPaths
    subset_dir = ProjectPaths.get_subset_dir(season, layer)

    # Clean orchestration directories to prevent stale data
    for script_name in [p.stem for p in step_dir.glob("process*.py")]:
        shutil.rmtree(project_root_path / 'figures' / step_dir.name / script_name, ignore_errors=True)
    import time
    time.sleep(1) # Wait for WSL to release directory locks

    # --- Group 20: Decorrelation Scale ---
    code = run_script(step_dir, env, 'process21_decorrelation_drivers.py', '--season', season, '--layer', layer)
    if code != 0: sys.exit(code)

    for target_region in target_regions:
        logging.info(f"=== Starting analysis for region: {target_region} ===")
        
        # --- Group 10: Trend Group Analysis ---
        code = run_script(step_dir, env, 'process11_trend_grouping_and_maps.py', '--target_region', target_region, '--season', season, '--layer', layer)
        if code != 0: sys.exit(code)
        
        code = run_script(step_dir, env, 'process12_pca_sensitivity.py', '--target_region', target_region, '--season', season, '--layer', layer)
        if code != 0: sys.exit(code)
        
        code = run_script(step_dir, env, 'process13_raw_sensitivity.py', '--target_region', target_region, '--season', season, '--layer', layer)
        if code != 0: sys.exit(code)
        
        code = run_script(step_dir, env, 'process14_significance_comparison.py', '--target_region', target_region, '--season', season, '--layer', layer)
        if code != 0: sys.exit(code)
        
        ts_params_df = pd.read_csv(step_dir / 'step5_ts_parameters.csv')
        for p_idx in range(len(ts_params_df)):
            code = run_script(step_dir, env, 'process15_parameter_timeseries_plotting.py', '--target_region', target_region, '--season', season, '--layer', layer, '--param_idx', str(p_idx))
            if code != 0: sys.exit(code)

        # --- Group 30: Correlation (Env & Nutr) ---
        for data_type in ['env', 'nutr']:
            logging.info(f"--- Group 30 & 40 for {data_type} in {target_region} ---")
            
            # Distribution
            code = run_script(step_dir, env, 'process31_correlation_distribution.py', '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type)
            if code != 0: sys.exit(code)
            
            # Chunked heatmaps
            chunk_idx = 0
            while True:
                code = run_script(step_dir, env, 'process33_correlation_heatmap.py', '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type, '--chunk_idx', str(chunk_idx))
                if code == 42:
                    break # Reached end of chunks
                elif code != 0:
                    sys.exit(code)
                chunk_idx += 1

            # Scatter Plots (Specific params)
            if data_type == 'env':
                scatter_params = ['Summer_Stratification', f'{season}_1_WTEMP', f'{season}_2_WTEMP', f'{season}_Chla_Corr_PC1']
            else:
                scatter_params = [f'{season}_2_DOC2', f'{season}_2_COD2', f'{season}_2_TN2', f'{season}_2_TP2']

            for pc in ['PC1', 'PC2']:
                df_path = subset_dir / f'pca_{data_type}_corr_{pc.lower()}.csv'
                if not df_path.exists(): continue
                df_corr = pd.read_csv(df_path, nrows=1)
                
                for param in scatter_params:
                    # process32 expects exact columns (process12 appended _Corr_PC1 but here we use base names if they exist)
                    actual_param = param.replace('_Corr_PC1', '') 
                    if actual_param in df_corr.columns:
                        run_script(step_dir, env, 'process32_loading_scatter_plots.py', '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type, '--param_col', actual_param, '--pc_name', pc)

            # --- Group 40: Spatial Maps ---
            for pc in ['PC1', 'PC2']:
                df_path = subset_dir / f'pca_{data_type}_corr_{pc.lower()}.csv'
                if not df_path.exists(): continue
                df_corr = pd.read_csv(df_path, nrows=1)
                parameters = [c for c in df_corr.columns if f"{c}_pval" in df_corr.columns]
                
                for param in parameters:
                    code = run_script(step_dir, env, 'process41_spatial_correlation_maps.py', '--pc_name', pc, '--param', param, '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type)
                    if code != 0: sys.exit(code)
                    
                    code = run_script(step_dir, env, 'process42_time_series_significant_stations_PC_correlation.py', '--pc_name', pc, '--param', param, '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type)
                    if code != 0: sys.exit(code)

                    code = run_script(step_dir, env, 'process43_confirm_env_parameter_relationship.py', '--pc_name', pc, '--param', param, '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type)
                    if code != 0: sys.exit(code)

    logging.info("All orchestrations completed successfully.")

if __name__ == "__main__":
    main()

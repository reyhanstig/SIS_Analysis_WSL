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
    
    param_file = step_dir / 'step5_parameter.csv'
    params = {}
    if param_file.exists():
        df_p = pd.read_csv(param_file)
        for _, row in df_p.iterrows():
            params[row['parameter_name']] = row['value']
            
    seasons = [s.strip() for s in params.get('seasons', 'Spring, Summer, Autumn, Winter').split(',')]
    layers = [l.strip() for l in params.get('layers', 'surface, bottom').split(',')]
    target_regions = [r.strip() for r in params.get('target_region', 'Seto Inland Sea').split(',')]

    if str(project_root_path) not in sys.path:
        sys.path.insert(0, str(project_root_path))
    from utils.paths import ProjectPaths

    for season in seasons:
        for layer in layers:
            subset_dir = ProjectPaths.get_subset_dir(season, layer)
            for target_region in target_regions:
                for data_type in ['env', 'nutr']:
                    for pc in ['PC1', 'PC2']:
                        df_path = subset_dir / f'pca_{data_type}_corr_{pc.lower()}.csv'
                        if not df_path.exists(): continue

                        run_script(step_dir, env, 'process41_spatial_correlation_maps.py', '--pc_name', pc, '--param', 'all', '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type)
                        run_script(step_dir, env, 'process42_time_series_significant_stations_PC_correlation.py', '--pc_name', pc, '--param', 'all', '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type)
                        run_script(step_dir, env, 'process43_confirm_env_parameter_relationship.py', '--pc_name', pc, '--param', 'all', '--target_region', target_region, '--season', season, '--layer', layer, '--data_type', data_type)

if __name__ == "__main__":
    main()

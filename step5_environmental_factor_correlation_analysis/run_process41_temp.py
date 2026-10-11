import os
import sys
import logging
from pathlib import Path
import subprocess

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
    
    if str(project_root_path) not in sys.path:
        sys.path.insert(0, str(project_root_path))
    from utils.paths import ProjectPaths

    # Hardcoded restrictions
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    layers = ['surface', 'bottom']
    target_regions = ['Seto Inland Sea']

    for season in seasons:
        for layer in layers:
            subset_dir = ProjectPaths.get_subset_dir(season.lower(), layer)
            for target_region in target_regions:
                for data_type in ['env', 'nutr']:
                    for pc in ['PC1', 'PC2']:
                        df_path = subset_dir / f'pca_{data_type}_corr_{pc.lower()}.csv'
                        if not df_path.exists(): continue

                        run_script(step_dir, env, 'process41_spatial_correlation_maps.py', '--pc_name', pc, '--param', 'all', '--target_region', target_region, '--season', season.lower(), '--layer', layer, '--data_type', data_type)

if __name__ == "__main__":
    main()

import sys
import subprocess
from pathlib import Path
import pandas as pd

step_dir = Path("/home/reyha/SIS_Analysis_WSL/step5_environmental_factor_correlation_analysis")
project_root_path = step_dir.parent

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

sys.path.insert(0, str(project_root_path))
from utils.paths import ProjectPaths
subset_dir = ProjectPaths.get_subset_dir(season, layer)

for target_region in target_regions:
    for data_type in ['env', 'nutr']:
        for pc in ['PC1', 'PC2']:
            df_path = subset_dir / f'pca_{data_type}_corr_{pc.lower()}.csv'
            if not df_path.exists(): continue
            df_corr = pd.read_csv(df_path, nrows=1)
            parameters = [c for c in df_corr.columns if f"{c}_pval" in df_corr.columns]
            
            for param in parameters:
                cmd = [sys.executable, str(step_dir / 'process41_spatial_correlation_maps.py'), 
                       '--pc_name', pc, '--param', param, '--target_region', target_region, 
                       '--season', season, '--layer', layer, '--data_type', data_type]
                print(f"Running process41 for {target_region}, {data_type}, {pc}, {param}")
                subprocess.run(cmd, cwd=str(step_dir))

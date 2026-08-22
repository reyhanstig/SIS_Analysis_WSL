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
    
    param_file = step_dir / 'step6_parameters.csv'
    if not param_file.exists():
        logging.error(f"Parameter file not found: {param_file}")
        sys.exit(1)
        
    df_params = pd.read_csv(param_file)
    
    # Clean output directories to prevent stale data for process02 and process03 ONLY
    for script_name in ['process02_time_series_significant_stations_PC_correlation', 'process03_confirm_env_parameter_relationship']:
        shutil.rmtree(project_root_path / 'figures' / step_dir.name / script_name, ignore_errors=True)
        shutil.rmtree(project_root_path / 'data' / 'processed' / step_dir.name / script_name, ignore_errors=True)
    import time
    time.sleep(1) # Wait for WSL to release directory locks

    process01_dir = project_root_path / 'data' / 'processed' / step_dir.name / 'process01_pc_driver_temporal_analysis'

    for _, row in df_params.iterrows():
        target_region = str(row['target_region'])
        pc_name = str(row['pc_name'])
        start_year = str(row['start_year'])
        end_year = str(row['end_year'])
        output_prefix = str(row['output_prefix'])
        
        logging.info(f"=== Starting analysis for: {output_prefix} {pc_name} {start_year}-{end_year} ===")
        
        # Process 02 & 03
        prefix_str = output_prefix.replace(' ', '_').replace('-', '_')
        year_period = f"{start_year}-{end_year}"
        
        corr_file = process01_dir / prefix_str / year_period / f"{prefix_str}_{pc_name}_{start_year}_{end_year}_correlations.csv"
        
        if not corr_file.exists():
            logging.warning(f"Correlation file not found: {corr_file}, skipping process02 and process03")
            continue
            
        df_corr = pd.read_csv(corr_file, nrows=1)
        parameters = [c for c in df_corr.columns if f"{c}_pval" in df_corr.columns]
        
        for param in parameters:
            # Process 02
            code = run_script(
                step_dir, env, 'process02_time_series_significant_stations_PC_correlation.py',
                '--target_region', target_region,
                '--pc_name', pc_name,
                '--start_year', start_year,
                '--end_year', end_year,
                '--output_prefix', output_prefix,
                '--param', param
            )
            if code != 0:
                sys.exit(code)
                
            # Process 03
            code = run_script(
                step_dir, env, 'process03_confirm_env_parameter_relationship.py',
                '--target_region', target_region,
                '--pc_name', pc_name,
                '--start_year', start_year,
                '--end_year', end_year,
                '--output_prefix', output_prefix,
                '--param', param
            )
            if code != 0:
                sys.exit(code)

    logging.info("All orchestrations completed successfully.")

if __name__ == "__main__":
    main()

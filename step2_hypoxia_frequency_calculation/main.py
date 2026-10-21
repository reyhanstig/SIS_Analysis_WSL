import os
import sys
import logging
import pandas as pd
from pathlib import Path
import subprocess

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    step_dir = Path(__file__).parent
    project_root = step_dir.parent
    
    global_scripts = [
        'process01_hypoxia_frequency_trend_area_fraction_global.py',
    ]
    
    per_bay_scripts = [
        'process11_mean_climatological_do_map.py',
        'process12_hypoxia_frequency_map.py',
        'process13_do_trend_spatial_mapping.py',
        'process14_hypoxia_tendency_per_station.py',
    ]
    # Scripts that also produce a figure for the entire Seto Inland Sea
    whole_area_scripts = {
        'process11_mean_climatological_do_map.py',
        'process12_hypoxia_frequency_map.py',
        'process13_do_trend_spatial_mapping.py',
    }
    
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{str(project_root)}{os.pathsep}{env.get('PYTHONPATH', '')}"
    
    # Run global scripts
    for script in global_scripts:
        script_path = step_dir / script
        logging.info(f"Running global script {script}...")
        result = subprocess.run([sys.executable, str(script_path)], cwd=str(step_dir), env=env)
        if result.returncode != 0:
            logging.error(f"Script {script} failed with exit code {result.returncode}")
            sys.exit(result.returncode)
            
    # Load basin division parameters from parameter file
    param_file = step_dir / "step2_parameter.csv"
    params = {}
    if param_file.exists():
        df_p = pd.read_csv(param_file)
        for _, row in df_p.iterrows():
            params[row['parameter_name']] = row['value']

    def _split(value):
        return [v.strip() for v in str(value).split(';') if v.strip()]

    whole_area = str(params.get('whole_area_region', 'Seto Inland Sea')).strip()
    bays = _split(params.get('bay_regions', 'Tokyo Bay;Ise Bay'))
    subbasins = _split(params.get('seto_inland_sea_subbasins', ''))
    plot_whole_area = str(params.get('plot_whole_area', 'True')).strip().lower() == 'true'

    regions_to_calculate = sorted(set(subbasins + bays))
    logging.info(f"Target divisions for per-bay scripts: {regions_to_calculate}")
    if plot_whole_area:
        logging.info(f"Whole-area region (process11-13): {whole_area}")

    for script in per_bay_scripts:
        script_path = step_dir / script
        targets = list(regions_to_calculate)
        if plot_whole_area and script in whole_area_scripts:
            targets = [whole_area] + targets
        for division in targets:
            logging.info(f"Running {script} for division: {division}...")
            result = subprocess.run([sys.executable, str(script_path), "--division", division], cwd=str(step_dir), env=env)
            if result.returncode != 0:
                logging.error(f"Script {script} failed for division {division} with exit code {result.returncode}")
                sys.exit(result.returncode)

    logging.info("All scripts completed successfully.")

if __name__ == "__main__":
    main()

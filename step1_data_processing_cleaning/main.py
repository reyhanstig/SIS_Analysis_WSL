import os
import sys
import logging
from pathlib import Path
import subprocess

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    scripts = [
        'process01_extract_spatial_data.py',
        'process02_create_seasonal_subset.py',
        'process03_extract_fixed_station.py',
        'process04_extract_hiroshima_survey.py',
        'process05_extract_line_survey.py',
        # 'process06_retrieve_sis_river_stations.py',
    ]
    
    step_dir = Path(__file__).parent
    
    for script in scripts:
        script_path = step_dir / script
        logging.info(f"Running {script}...")
        env = os.environ.copy()
        project_root = str(step_dir.parent)
        env['PYTHONPATH'] = f"{project_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
        
        result = subprocess.run([sys.executable, str(script_path)], cwd=str(step_dir), env=env)
        if result.returncode != 0:
            logging.error(f"Script {script} failed with exit code {result.returncode}")
            sys.exit(result.returncode)
            
    logging.info("All scripts completed successfully.")

if __name__ == "__main__":
    main()

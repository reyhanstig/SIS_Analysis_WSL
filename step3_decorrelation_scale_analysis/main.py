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
        '10_calculate_bay_decorrelation_scales.py',
        '20_decorrelation_analysis_permutations.py',
        '30_decorrelation_seasonal.py',
    ]
    
    per_bay_scripts = [
        '40_calculate_decorrelation_scale_per_bay.py',
        '50_plot_decorrelation_scale_complete.py',
    ]
    
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
            
    # Load divisions from parameter file
    param_file = step_dir / "step3_parameter.csv"
    divisions = ["Seto Inland Sea", "Tokyo Bay", "Ise Bay", "Osaka Bay"]
    if param_file.exists():
        df_p = pd.read_csv(param_file)
        params = {}
        for _, row in df_p.iterrows():
            params[row['parameter_name']] = row['value']
        if 'divisions' in params:
            divisions = [d.strip() for d in params['divisions'].split(',')]
            
    # Because script 40 calculates explicitly for each unique division *within* the SIS if "Seto Inland Sea" is provided,
    # and the original script 40 looped through them, we need to pass the divisions exactly as they come.
    # The new script 40 logic takes --division and processes that specific division.
    # However, Seto Inland Sea might need special handling. Let's look at the old logic:
    # "Separate all watermasses into their individual divisions/basins"
    # Actually, the user's dataset has watermass_name vs division. 
    # If the user passes "Seto Inland Sea", script 40 might need to know to compute the sub-regions.
    # But wait, script 40's `compute_decorrelation_for_division` filters by:
    # `merged_gdf['watermass_name'] == db_division | merged_gdf['division'] == db_division`
    # If we pass "Seto Inland Sea", it filters by watermass_name='Seto Inland Sea', which means it includes ALL of SIS!
    # In the original 40, there was logic:
    # for div in divisions:
    #     if div == 'Seto Inland Sea':
    #         sis_divs = merged_gdf[merged_gdf['watermass_name'] == 'Seto Inland Sea']['division'].dropna().unique()
    #         regions_to_calculate.update(sis_divs)
    # We should expand divisions in main.py before looping!

    import geopandas as gpd
    merged_gdf = None
    try:
        sys.path.insert(0, str(project_root))
        from utils.data_loader import load_and_process_data
        merged_gdf = load_and_process_data(force_reload=False)
    except Exception as e:
        logging.warning(f"Could not load data to expand regions: {e}")
        
    regions_to_calculate = set()
    for div in divisions:
        if div == 'Seto Inland Sea' and merged_gdf is not None:
            sis_divs = merged_gdf[merged_gdf['watermass_name'] == 'Seto Inland Sea']['division'].dropna().unique()
            regions_to_calculate.update(sis_divs)
        else:
            regions_to_calculate.add(div)
            
    regions_to_calculate = sorted(list(regions_to_calculate))
    logging.info(f"Target divisions for per-bay scripts: {regions_to_calculate}")

    for script in per_bay_scripts:
        script_path = step_dir / script
        for division in regions_to_calculate:
            logging.info(f"Running {script} for division: {division}...")
            result = subprocess.run([sys.executable, str(script_path), "--division", division], cwd=str(step_dir), env=env)
            if result.returncode != 0:
                logging.error(f"Script {script} failed for division {division} with exit code {result.returncode}")
                # We can choose to exit or continue. Let's continue for other divisions, but maybe we should fail fast.
                # Let's fail fast to be safe.
                sys.exit(result.returncode)

    logging.info("All scripts completed successfully.")

if __name__ == "__main__":
    main()

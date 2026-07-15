import sys
import subprocess
from pathlib import Path
import pandas as pd

step_dir = Path("/home/reyha/SIS_Analysis_WSL/step2_hypoxia_frequency_calculation")
scripts = [
    'process11_mean_climatological_do_map.py',
    'process12_hypoxia_frequency_map.py',
    'process13_do_trend_spatial_mapping.py'
]

project_root = step_dir.parent
sys.path.insert(0, str(project_root))
from utils.data_loader import load_and_process_data
merged_gdf = load_and_process_data(force_reload=False)

divisions = ["Seto Inland Sea", "Tokyo Bay", "Ise Bay", "Osaka Bay"]
regions_to_calculate = set()
for div in divisions:
    if div == 'Seto Inland Sea' and merged_gdf is not None:
        sis_divs = merged_gdf[merged_gdf['watermass_name'] == 'Seto Inland Sea']['division'].dropna().unique()
        regions_to_calculate.update(sis_divs)
    else:
        regions_to_calculate.add(div)

regions_to_calculate = sorted(list(regions_to_calculate))

for script in scripts:
    for division in regions_to_calculate:
        print(f"Running {script} for division: {division}...")
        subprocess.run([sys.executable, str(step_dir / script), "--division", division], cwd=str(step_dir))

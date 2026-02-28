import sys
import yaml
import subprocess
import papermill as pm
from pathlib import Path

def run_step(notebook_path, output_path, section=None):
    params = {}
    if section:
        with open("params.yaml", "r") as f:
            all_params = yaml.safe_load(f)
            params = all_params.get(section, {})
    
    print(f"Running {notebook_path} with params: {params}")
    
    pm.execute_notebook(
        notebook_path,
        output_path,
        parameters=params,
        kernel_name='python3'  # Or 'sis_analysis' if registered
    )

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/run_pipeline_step.py <notebook> <output> [section]")
        sys.exit(1)
        
    ntbk = sys.argv[1]
    out = sys.argv[2]
    sect = sys.argv[3] if len(sys.argv) > 3 else None
    
    run_step(ntbk, out, sect)

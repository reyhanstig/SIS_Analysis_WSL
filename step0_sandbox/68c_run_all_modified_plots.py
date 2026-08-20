import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    project_root = Path('/home/reyha/SIS_Analysis_WSL')
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{str(project_root)}{os.pathsep}{env.get('PYTHONPATH', '')}"

    steps = [
        "step2_hypoxia_frequency_calculation",
        "step3_decorrelation_scale_analysis",
        "step4_PCA_analysis",
        "step5_environmental_factor_correlation_analysis",
        "step6_pick_up_area_location"
    ]

    for step in steps:
        step_dir = project_root / step
        logging.info(f"========== Running orchestrator for {step} ==========")
        cmd = [sys.executable, "-m", "main"]
        result = subprocess.run(cmd, cwd=str(step_dir), env=env)
        
        if result.returncode != 0:
            logging.error(f"Orchestrator for {step} failed with exit code {result.returncode}")
            sys.exit(result.returncode)
            
    logging.info("========== All steps completed successfully ==========")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import shutil
import argparse
from pathlib import Path

def delete_pipeline_step(target_path):
    project_root = Path(__file__).resolve().parent.parent
    target = Path(target_path)
    
    if not target.is_absolute():
        target = project_root / target
        
    if not target.exists():
        print(f"Error: Target '{target}' does not exist.")
        sys.exit(1)

    try:
        relative_target = target.relative_to(project_root)
    except ValueError:
        print(f"Error: Target '{target}' is not within the project root '{project_root}'.")
        sys.exit(1)

    is_script = target.is_file()
    
    # 1. Delete the source
    print(f"Deleting source: {target}")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    # Determine base relative path without extension if it's a script
    if is_script and relative_target.suffix == '.py':
        base_relative = relative_target.with_suffix('')
    else:
        base_relative = relative_target

    # 2. Delete Processed Data
    data_dir = project_root / "data" / "processed" / base_relative
    if data_dir.exists():
        print(f"Deleting processed data: {data_dir}")
        if data_dir.is_dir():
            shutil.rmtree(data_dir)
        else:
            data_dir.unlink()
    else:
        print(f"No processed data found at {data_dir}, skipping.")

    # 3. Delete Figures
    fig_dir = project_root / "figures" / base_relative
    if fig_dir.exists():
        print(f"Deleting figures: {fig_dir}")
        if fig_dir.is_dir():
            shutil.rmtree(fig_dir)
        else:
            fig_dir.unlink()
    else:
        print(f"No figures found at {fig_dir}, skipping.")

    print("\nDeletion operation completed successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safely delete a pipeline step folder or script and its outputs.")
    parser.add_argument("--target", required=True, help="The path to the step folder or script (e.g., step1_data_processing or step3_PCA_analysis/10_PCA_analysis.py)")
    
    args = parser.parse_args()
    delete_pipeline_step(args.target)

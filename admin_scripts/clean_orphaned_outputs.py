#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

def clean_orphaned_outputs():
    project_root = Path(__file__).resolve().parent.parent
    processed_dir = project_root / "data" / "processed"
    figures_dir = project_root / "figures"

    # We only care about step folders (e.g., step1_..., step2_...)
    # They mirror the structure in project_root.
    
    deleted_count = 0

    for base_output_dir in [processed_dir, figures_dir]:
        if not base_output_dir.exists():
            continue

        for step_dir in base_output_dir.iterdir():
            if not step_dir.is_dir() or not step_dir.name.startswith("step"):
                continue

            # Check if the main step folder exists in the project root
            source_step_dir = project_root / step_dir.name
            if not source_step_dir.exists():
                print(f"Orphaned step folder found: {step_dir}")
                print(f"-> Source '{source_step_dir}' does not exist. Deleting...")
                shutil.rmtree(step_dir)
                deleted_count += 1
                continue

            # If the step folder exists, check for individual script output folders
            # Assuming output folders within step folders match the script names without '.py'
            for output_sub in step_dir.iterdir():
                if not output_sub.is_dir() and not output_sub.is_file():
                    continue

                source_script = source_step_dir / f"{output_sub.name}.py"
                source_folder = source_step_dir / output_sub.name
                
                # Special cases or subdirectories might exist, but usually it's .py
                if not source_script.exists() and not source_folder.exists():
                    print(f"Orphaned output found: {output_sub}")
                    print(f"-> Source '{source_script}' or '{source_folder}' does not exist. Deleting...")
                    if output_sub.is_dir():
                        shutil.rmtree(output_sub)
                    else:
                        output_sub.unlink()
                    deleted_count += 1

    print(f"\nCleanup complete. Deleted {deleted_count} orphaned output items.")

if __name__ == "__main__":
    clean_orphaned_outputs()

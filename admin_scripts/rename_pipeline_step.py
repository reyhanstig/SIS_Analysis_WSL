#!/usr/bin/env python3
import os
import sys
import shutil
import argparse
from pathlib import Path
import re

def rename_pipeline_step(old_name, new_name):
    project_root = Path(__file__).resolve().parent.parent

    # 1. Rename Source Folder
    old_dir = project_root / old_name
    new_dir = project_root / new_name

    if not old_dir.exists():
        print(f"Error: Directory '{old_dir}' does not exist.")
        sys.exit(1)

    if new_dir.exists():
        print(f"Error: Target directory '{new_dir}' already exists.")
        sys.exit(1)

    print(f"Renaming source folder: {old_name} -> {new_name}")
    old_dir.rename(new_dir)

    # 2. Migrate Processed Data Folder
    old_data_dir = project_root / "data" / "processed" / old_name
    new_data_dir = project_root / "data" / "processed" / new_name
    if old_data_dir.exists():
        print(f"Migrating data: {old_data_dir} -> {new_data_dir}")
        old_data_dir.rename(new_data_dir)
    else:
        print(f"No processed data found at {old_data_dir}, skipping.")

    # 3. Migrate Figures Folder
    old_fig_dir = project_root / "figures" / old_name
    new_fig_dir = project_root / "figures" / new_name
    if old_fig_dir.exists():
        print(f"Migrating figures: {old_fig_dir} -> {new_fig_dir}")
        old_fig_dir.rename(new_fig_dir)
    else:
        print(f"No figures found at {old_fig_dir}, skipping.")

    # 4. Update dvc.yaml
    dvc_yaml_path = project_root / "dvc.yaml"
    if dvc_yaml_path.exists():
        print(f"Updating dvc.yaml...")
        with open(dvc_yaml_path, 'r', encoding='utf-8') as f:
            dvc_content = f.read()

        # Simple string replacement since stage names, deps, and cmds match the folder name exactly
        dvc_content = dvc_content.replace(old_name, new_name)

        with open(dvc_yaml_path, 'w', encoding='utf-8') as f:
            f.write(dvc_content)
    else:
        print("dvc.yaml not found, skipping.")

    # 5. Update pipeline_details.md and README.md
    docs_to_update = [
        project_root / "pipeline_details.md",
        project_root / "README.md"
    ]

    for doc in docs_to_update:
        if doc.exists():
            print(f"Updating documentation: {doc.name}")
            with open(doc, 'r', encoding='utf-8') as f:
                content = f.read()

            content = content.replace(old_name, new_name)

            with open(doc, 'w', encoding='utf-8') as f:
                f.write(content)

    print("\nRename operation completed successfully!")
    print("If you had any .dvc files explicitly tracking outputs for this step, please verify them.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safely rename a DVC pipeline step folder and migrate its outputs.")
    parser.add_argument("--old_name", required=True, help="The current name of the step folder (e.g., step1_data_extraction)")
    parser.add_argument("--new_name", required=True, help="The new name for the step folder (e.g., step1_data_processing)")
    
    args = parser.parse_args()
    rename_pipeline_step(args.old_name, args.new_name)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pdfplumber
import pandas as pd
import re
from pathlib import Path


# --- BOILERPLATE INJECTED BY AGENT ---
import os
import sys
import pandas as pd
import logging
import matplotlib.pyplot as plt
from pathlib import Path

CURRENT_SCRIPT = Path(__file__).resolve()
# Fix namespace shadowing by inserting project root at index 0
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
import shutil
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
if PROCESSED_DATA_DIR.exists():
    shutil.rmtree(PROCESSED_DATA_DIR, ignore_errors=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')

param_file = CURRENT_SCRIPT.parent / f"step{step_num}_parameter.csv"
PARAMS = {}
if param_file.exists():
    df_params = pd.read_csv(param_file)
    if 'parameter_name' in df_params.columns and 'value' in df_params.columns:
        for _, row in df_params.iterrows():
            PARAMS[row['parameter_name']] = row['value']
# -------------------------------------
try:
    from utils.paths import ProjectPaths
except ImportError:
    from utils.paths import ProjectPaths

def extract_fixed_line_survey(pdf_path, output_csv):
    # Pages 3 to 14 typically contain the 12 months of Table 3 data (General Items)
    target_pages = range(2, 14) # pdfplumber uses 0-based indexing (Page 3 = index 2)
    
    all_data = []
    depth_labels = ["0m", "5m", "10m", "20m", "30m", "Bottom"]
    
    with pdfplumber.open(pdf_path) as pdf:
        for month_idx, page_num in enumerate(target_pages, start=1):
            page = pdf.pages[page_num]
            
            # Extract the table from the page
            tables = page.extract_tables()
            if not tables:
                print(f"Warning: No table found on page {page_num + 1}")
                continue
                
            # Assuming the main grid is the first table found on these pages
            table = tables[0]
            
            # Clean up and reverse the table cells character-by-character
            # (pdfplumber extracts text right-to-left due to layout/font encoding in this PDF)
            cleaned_table = []
            for row in table:
                cleaned_row = []
                for cell in row:
                    if cell is None:
                        cleaned_row.append("")
                    else:
                        rev_cell = cell[::-1].replace('\n', ' ').strip()
                        cleaned_row.append(rev_cell)
                cleaned_table.append(cleaned_row)
            
            # Parse each row for Station data (looking for St. <num> in column 1)
            for row in cleaned_table:
                if len(row) < 18:
                    continue
                
                station_cell = row[1]
                match = re.search(r'St\.\s*(\d+)', station_cell)
                if match:
                    station_id = int(match.group(1))
                    
                    # Temperature: columns 6 to 11 (0m, 5m, 10m, 20m, 30m, Bottom)
                    for idx, depth_label in enumerate(depth_labels):
                        val = row[6 + idx]
                        clean_val = re.sub(r'[^\d\.]', '', val)
                        if clean_val:
                            all_data.append({
                                "Month": month_idx,
                                "Station": station_id,
                                "Depth": depth_label,
                                "Variable": "Temperature",
                                "Value": float(clean_val)
                            })
                    
                    # Salinity: columns 12 to 17 (0m, 5m, 10m, 20m, 30m, Bottom)
                    for idx, depth_label in enumerate(depth_labels):
                        val = row[12 + idx]
                        clean_val = re.sub(r'[^\d\.]', '', val)
                        if clean_val:
                            all_data.append({
                                "Month": month_idx,
                                "Station": station_id,
                                "Depth": depth_label,
                                "Variable": "Salinity",
                                "Value": float(clean_val)
                            })

    # Create a DataFrame from the extracted long list
    df = pd.DataFrame(all_data)
    
    # Pivot the Variable column to have Temperature and Salinity as separate columns
    if not df.empty:
        df_pivot = df.pivot_table(
            index=["Month", "Station", "Depth"], 
            columns="Variable", 
            values="Value"
        ).reset_index()
        
        # Sort for clean reading
        df_pivot["Month"] = df_pivot["Month"].astype(int)
        df_pivot["Station"] = df_pivot["Station"].astype(int)
        
        # Custom sorting logic for depth to keep 0m, 5m, 10m, 20m, 30m, Bottom in order
        depth_order = {"0m": 0, "5m": 1, "10m": 2, "20m": 3, "30m": 4, "Bottom": 5}
        df_pivot["Depth_Order"] = df_pivot["Depth"].map(depth_order)
        
        df_pivot = df_pivot.sort_values(by=["Month", "Station", "Depth_Order"]).drop(columns=["Depth_Order"])
        
        # Ensure output directory exists
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV
        df_pivot.to_csv(output_csv, index=False, float_format='%.2f')
        print(f"Data successfully extracted to {output_csv}")
    else:
        print("No data was extracted. The table structure might need closer inspection.")

# Run the script
if __name__ == "__main__":
    survey_dir = ProjectPaths.DATA_DIR / "raw" / "Fixed_line_survey"
    pdf_filename = survey_dir / PARAMS.get("osaka_pdf_filename", "h28-all.pdf")
    output_filename = PROCESSED_DATA_DIR / "fixed_line_survey_long_osaka.csv"
    
    print(f"Extracting survey data from {pdf_filename}...")
    extract_fixed_line_survey(pdf_filename, output_filename)
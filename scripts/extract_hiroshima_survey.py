import pdfplumber
import pandas as pd
import re
from pathlib import Path

try:
    from scripts.paths import ProjectPaths
except ImportError:
    from paths import ProjectPaths

def group_words_by_line(words, threshold=3):
    if not words:
        return []
    words = sorted(words, key=lambda w: w['top'])
    lines = []
    current_line = [words[0]]
    for w in words[1:]:
        if w['top'] - current_line[-1]['top'] < threshold:
            current_line.append(w)
        else:
            lines.append(current_line)
            current_line = [w]
    lines.append(current_line)
    
    formatted_lines = []
    for line in lines:
        line_sorted = sorted(line, key=lambda w: w['x0'])
        text = " ".join([w['text'] for w in line_sorted])
        avg_top = sum([w['top'] for w in line_sorted]) / len(line_sorted)
        formatted_lines.append((text, avg_top))
    return formatted_lines

def clean_depth(depth_str):
    d = depth_str.replace(" ", "").strip()
    if d == "B-1m":
        return "Bottom"
    return d

def extract_hiroshima_survey(pdf_path, output_csv):
    explicit_v = [86.88, 107.28, 130.1, 152.9, 175.7, 198.5, 221.33, 244.13, 266.93, 289.73, 312.53, 335.35, 358.15, 380.95, 403.75, 426.58, 449.38, 472.18, 494.98, 517.8, 540.96]
    
    all_records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            month = page_idx + 1
            tables = page.find_tables(table_settings={
                "vertical_strategy": "explicit",
                "explicit_vertical_lines": explicit_v,
            })
            
            if not tables:
                print(f"Warning: No tables found on Page {month}")
                continue
                
            table = tables[0]
            words = page.extract_words()
            
            # Map words to cell coordinates
            cell_words = {}
            for w in words:
                mid_x = (w['x0'] + w['x1']) / 2
                mid_y = (w['top'] + w['bottom']) / 2
                
                for r_idx, row in enumerate(table.rows):
                    for c_idx, cell in enumerate(row.cells):
                        if cell is not None:
                            # cell is (x0, y0, x1, y1)
                            if cell[0] <= mid_x <= cell[2] and cell[1] <= mid_y <= cell[3]:
                                if (r_idx, c_idx) not in cell_words:
                                    cell_words[(r_idx, c_idx)] = []
                                cell_words[(r_idx, c_idx)].append(w)
                                break
                                
            # Extract station mapping from Row 1
            stations = {}
            for col_idx in range(1, 20):
                c_words = cell_words.get((1, col_idx), [])
                if c_words:
                    lines = group_words_by_line(c_words)
                    if lines:
                        first_line = lines[0][0]
                        match = re.search(r'\d+', first_line)
                        if match:
                            stations[col_idx] = int(match.group(0))
                            
            # Process Row 3 (Temperature), Row 4 (DO), Row 5 (Salinity)
            var_rows = {
                3: "Temperature",
                4: "DO",
                5: "Salinity"
            }
            
            for row_idx, var_name in var_rows.items():
                col0_words = cell_words.get((row_idx, 0), [])
                depth_lines = group_words_by_line(col0_words)
                
                # Check for each station column
                for col_idx in range(1, 20):
                    station_id = stations.get(col_idx)
                    if station_id is None:
                        continue
                        
                    c_words = cell_words.get((row_idx, col_idx), [])
                    
                    # Align each numeric word to its closest depth label
                    for w in c_words:
                        val_text = w['text']
                        # Check if it represents a valid number
                        clean_val = re.sub(r'[^\d\.]', '', val_text)
                        if not clean_val:
                            continue
                            
                        val_num = float(clean_val)
                        val_y = w['top']
                        
                        # Find closest depth label y-coordinate
                        best_depth_label = None
                        min_diff = 999.0
                        for depth_text, depth_y in depth_lines:
                            diff = abs(val_y - depth_y)
                            if diff < min_diff:
                                min_diff = diff
                                best_depth_label = depth_text
                                
                        # We only map if it matches a depth line within 8.0 points
                        if best_depth_label is not None and min_diff < 8.0:
                            clean_d = clean_depth(best_depth_label)
                            all_records.append({
                                "Month": month,
                                "Station": station_id,
                                "Depth": clean_d,
                                "Variable": var_name,
                                "Value": val_num
                            })
                            
    # Format and save to CSV
    if all_records:
        df = pd.DataFrame(all_records)
        df_pivot = df.pivot_table(
            index=["Month", "Station", "Depth"],
            columns="Variable",
            values="Value"
        ).reset_index()
        
        # Ensure all columns exist, even if some were completely empty (just in case)
        for col in ["Temperature", "Salinity", "DO"]:
            if col not in df_pivot.columns:
                df_pivot[col] = None
                
        # Sort values properly
        depth_order = {"0m": 0, "2m": 1, "5m": 2, "10m": 3, "20m": 4, "30m": 5, "Bottom": 6}
        df_pivot["Depth_Order"] = df_pivot["Depth"].map(depth_order)
        df_pivot = df_pivot.sort_values(by=["Month", "Station", "Depth_Order"]).drop(columns=["Depth_Order"])
        
        # Save to CSV
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_pivot.to_csv(output_path, index=False, float_format='%.2f')
        print(f"Extraction complete. Saved {len(df_pivot)} rows to {output_csv}")
    else:
        print("No records extracted.")

# Run the script
if __name__ == "__main__":
    survey_dir = ProjectPaths.DATA_DIR / "raw" / "Fixed_line_survey"
    pdf_filename = survey_dir / "587628.pdf"
    output_filename = survey_dir / "fixed_line_survey_long_hiroshima.csv"
    
    print(f"Extracting Hiroshima survey data from {pdf_filename}...")
    extract_hiroshima_survey(pdf_filename, output_filename)

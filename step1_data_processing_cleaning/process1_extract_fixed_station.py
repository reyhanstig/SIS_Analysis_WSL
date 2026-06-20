import pdfplumber
import pandas as pd
import re
import calendar
from pathlib import Path

try:
    from utils.paths import ProjectPaths
except ImportError:
    from utils.paths import ProjectPaths

def extract_fixed_station_observations(pdf_path, output_csv):
    # Pages 22 to 33 contain the 12 months of Table 2 data (気象・海象の定置観測)
    target_pages = range(21, 33) # pdfplumber uses 0-based indexing (Page 22 = index 21)
    
    all_rows = []
    
    # Map variable names to row indices in the table (15 rows total)
    row_mapping = {
        "Remarks": 0,
        "Salinity_Avg_PSU": 1,
        "Salinity_9am_PSU": 2,
        "Water_Temp_Avg_C": 3,
        "Water_Temp_9am_C": 4,
        "Wind_Speed_10min_Avg_m_s": 5,
        "Wind_Dir_10min_Max": 6,
        "Wind_Speed_10min_Max_m_s": 7,
        "Solar_Radiation_MJ_m2": 8,
        "Rainfall_mm": 9,
        "Air_Pressure_Avg_hPa": 10,
        "Humidity_Avg_pct": 11,
        "Air_Temp_Avg_C": 12,
        "Air_Temp_9am_C": 13
    }
    
    def clean_val(val, is_numeric=True):
        if not val or val == "－" or val == "-":
            return None
        if is_numeric:
            clean = re.sub(r'[^\d\.]', '', val)
            return float(clean) if clean else None
        return val

    with pdfplumber.open(pdf_path) as pdf:
        for month_idx, page_num in enumerate(target_pages, start=1):
            page = pdf.pages[page_num]
            tables = page.find_tables()
            if not tables:
                print(f"Warning: No table found on page {page_num + 1}")
                continue
                
            table = tables[0]
            words = page.extract_words()
            
            days_in_month = calendar.monthrange(2016, month_idx)[1]
            
            # Map cells by row and column index using midpoint-based matching
            cells_data = {}
            for cell in table.cells:
                # cell is a tuple: (x0, y0, x1, y1)
                
                # Find row_idx by finding row overlapping with cell center vertically
                # and selecting the row with the smallest height to handle merged cells
                cy = (cell[1] + cell[3]) / 2
                overlapping_rows = []
                for r_idx, r in enumerate(table.rows):
                    if r.bbox[1] - 1 <= cy <= r.bbox[3] + 1:
                        overlapping_rows.append((r_idx, r.bbox[3] - r.bbox[1]))
                row_idx = sorted(overlapping_rows, key=lambda x: x[1])[0][0] if overlapping_rows else -1
                
                # Find col_idx by finding col overlapping with cell center horizontally
                # and selecting the column with the smallest width to handle merged cells
                cx = (cell[0] + cell[2]) / 2
                overlapping_cols = []
                for c_idx, c in enumerate(table.columns):
                    if c.bbox[0] - 1 <= cx <= c.bbox[2] + 1:
                        overlapping_cols.append((c_idx, c.bbox[2] - c.bbox[0]))
                col_idx = sorted(overlapping_cols, key=lambda x: x[1])[0][0] if overlapping_cols else -1
                
                if row_idx == -1 or col_idx == -1:
                    continue
                    
                # Find all words that fall within the cell boundaries
                cell_words = []
                for w in words:
                    w_cx = (w['x0'] + w['x1']) / 2
                    w_cy = (w['top'] + w['bottom']) / 2
                    if cell[0] - 1 <= w_cx <= cell[2] + 1 and cell[1] - 1 <= w_cy <= cell[3] + 1:
                        cell_words.append(w)
                        
                # Sort words by x0 coordinate to ensure left-to-right reading order inside the cell
                cell_words.sort(key=lambda w: w['x0'])
                # Reverse each word to decode right-to-left character rendering
                cell_text_list = [w['text'][::-1].strip() for w in cell_words]
                
                if row_idx not in cells_data:
                    cells_data[row_idx] = {}
                cells_data[row_idx][col_idx] = (cell_text_list, cell_words)
                
            # Parse daily data for days 1 to days_in_month
            daily_records = {day: {"Month": month_idx, "Date": str(day)} for day in range(1, days_in_month + 1)}
            
            # Summary records (decade and monthly averages/sums)
            summary_records = {
                "First_10_Days_Avg": {"Month": month_idx, "Date": "First_10_Days_Avg"},
                "Middle_10_Days_Avg": {"Month": month_idx, "Date": "Middle_10_Days_Avg"},
                "Last_10_Days_Avg": {"Month": month_idx, "Date": "Last_10_Days_Avg"},
                "Monthly_Avg": {"Month": month_idx, "Date": "Monthly_Avg"}
            }
            
            for var_name, r_idx in row_mapping.items():
                is_numeric = (var_name != "Remarks" and var_name != "Wind_Dir_10min_Max")
                
                # Column 2: Days 1-10 (Day 10 down to Day 1)
                col2_data = cells_data.get(r_idx, {}).get(2, ([], []))
                col2_vals = list(reversed(col2_data[0]))
                for i, val in enumerate(col2_vals):
                    day = i + 1
                    daily_records[day][var_name] = clean_val(val, is_numeric)
                    
                # Column 4: Days 11-20
                col4_data = cells_data.get(r_idx, {}).get(4, ([], []))
                col4_vals = col4_data[0]
                col4_words = col4_data[1]
                # If cell elements match exactly 10, map sequentially.
                # Otherwise, fallback to precise coordinate-based mapping.
                if len(col4_vals) == 10:
                    for i, val in enumerate(col4_vals):
                        day = i + 11
                        daily_records[day][var_name] = clean_val(val, is_numeric)
                else:
                    for val, w in zip(col4_vals, col4_words):
                        day = 11 + round((w['x0'] - 246.3) / 10.27)
                        if 11 <= day <= 20:
                            daily_records[day][var_name] = clean_val(val, is_numeric)
                            
                # Column 6: Days 21 to end of month
                col6_data = cells_data.get(r_idx, {}).get(6, ([], []))
                col6_vals = col6_data[0]
                col6_words = col6_data[1]
                expected_days = days_in_month - 20
                if len(col6_vals) == expected_days:
                    for i, val in enumerate(col6_vals):
                        day = i + 21
                        daily_records[day][var_name] = clean_val(val, is_numeric)
                else:
                    for val, w in zip(col6_vals, col6_words):
                        day = 21 + round((w['x0'] - 359.4) / 10.27)
                        if 21 <= day <= days_in_month:
                            daily_records[day][var_name] = clean_val(val, is_numeric)
                            
                # Col 3: First_10_Days_Avg
                col3_val = cells_data.get(r_idx, {}).get(3, ([], []))[0]
                summary_records["First_10_Days_Avg"][var_name] = clean_val(col3_val[0], is_numeric) if col3_val else None
                
                # Col 5: Middle_10_Days_Avg
                col5_val = cells_data.get(r_idx, {}).get(5, ([], []))[0]
                summary_records["Middle_10_Days_Avg"][var_name] = clean_val(col5_val[0], is_numeric) if col5_val else None
                
                # Col 7: Last_10_Days_Avg
                col7_val = cells_data.get(r_idx, {}).get(7, ([], []))[0]
                summary_records["Last_10_Days_Avg"][var_name] = clean_val(col7_val[0], is_numeric) if col7_val else None
                
                # Col 8: Monthly_Avg
                col8_val = cells_data.get(r_idx, {}).get(8, ([], []))[0]
                summary_records["Monthly_Avg"][var_name] = clean_val(col8_val[0], is_numeric) if col8_val else None
                
            # Append daily rows and decade summaries in chronological order
            for day in range(1, days_in_month + 1):
                all_rows.append(daily_records[day])
                if day == 10:
                    all_rows.append(summary_records["First_10_Days_Avg"])
                elif day == 20:
                    all_rows.append(summary_records["Middle_10_Days_Avg"])
                elif day == days_in_month:
                    all_rows.append(summary_records["Last_10_Days_Avg"])
                    all_rows.append(summary_records["Monthly_Avg"])
                    
    # Create DataFrame
    df = pd.DataFrame(all_rows)
    
    # Ensure correct columns order (matching original line_survey_osaka.csv order, with Month first)
    cols = [
        "Month", "Date", "Air_Temp_9am_C", "Air_Temp_Avg_C", "Humidity_Avg_pct",
        "Air_Pressure_Avg_hPa", "Rainfall_mm", "Solar_Radiation_MJ_m2",
        "Wind_Speed_10min_Max_m_s", "Wind_Dir_10min_Max", "Wind_Speed_10min_Avg_m_s",
        "Water_Temp_9am_C", "Water_Temp_Avg_C", "Salinity_9am_PSU", "Salinity_Avg_PSU",
        "Remarks"
    ]
    df = df[cols]
    
    # Ensure parent output directory exists
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    
    # Save to CSV
    df.to_csv(output_csv, index=False)
    print(f"Daily fixed station observations successfully saved to {output_csv}")

if __name__ == "__main__":
    survey_dir = ProjectPaths.DATA_DIR / "raw" / "Fixed_line_survey"
    pdf_filename = survey_dir / "h28-all.pdf"
    output_filename = survey_dir / "fixed_station_observations_osaka.csv"
    
    print(f"Extracting daily fixed station data from {pdf_filename}...")
    extract_fixed_station_observations(pdf_filename, output_filename)

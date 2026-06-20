import pandas as pd
import geopandas as gpd
import os
import glob
from pathlib import Path
from .paths import ProjectPaths

def get_season(month):
    """
    Map month number to season.
    Spring: 3, 4, 5
    Summer: 6, 7, 8
    Autumn: 9, 10, 11
    Winter: 12, 1, 2
    """
    if month in [3, 4, 5]:
        return 'Spring'
    elif month in [6, 7, 8]:
        return 'Summer'
    elif month in [9, 10, 11]:
        return 'Autumn'
    else:
        return 'Winter'

def load_raw_shapefiles(start_year=1981, end_year=2023):
    """
    Load and concatenate raw shapefiles from the environmental_data directory.
    Aggregates data across the specified year range.
    """
    print(f"Loading raw shapefiles from {start_year} to {end_year}...")
    
    # Ensure water manual exists
    if not ProjectPaths.WATER_MANUAL_PATH.exists():
        print(f"Warning: Water manual not found at {ProjectPaths.WATER_MANUAL_PATH}")

    all_years_data = []

    # Ensure processed directory exists
    ProjectPaths.ensure_directories()

    for year in range(start_year, end_year + 1):
        # Construct path pattern: data/raw/environmental_data/{year}_*/*.shp
        search_path = ProjectPaths.RAW_DATA_DIR / f"{year}_*" / "*.shp"
        files = glob.glob(str(search_path))
        
        if not files:
            # print(f"No files found for year {year}") # Optional: reduce verbosity
            continue
            
        for file_path in files:
            try:
                gdf = gpd.read_file(file_path)
                
                # Add year column derived from loop/directory structure
                gdf['year'] = year
                
                # Standardize columns if necessary (basic check)
                if 'surveymont' in gdf.columns:
                     # Ensure surveymont is numeric for season calculation
                     gdf['surveymont'] = pd.to_numeric(gdf['surveymont'], errors='coerce')
                
                all_years_data.append(gdf)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")

    if not all_years_data:
        raise ValueError("No data loaded. Check paths and year range.")

    print(f"Merging {len(all_years_data)} shapefiles...")
    merged_gdf = pd.concat(all_years_data, ignore_index=True)

    # --- Load Water Mass Codes ---
    manual_filepath = ProjectPaths.WATER_MANUAL_PATH
    if manual_filepath.exists():
        codes_df = pd.read_excel(manual_filepath, sheet_name='3. Water mass code', header=3)
        codes_df = codes_df.rename(columns={
            'Water Mass Code': 'watercode',
            'Water Mass Name': 'watermass_name',
            'Water Mass Division': 'division',
            'Water Mass Details': 'details'
        })
        
        # Ensure 'watercode' and columns are int before merge
        if 'watercode' in merged_gdf.columns and 'watercode' in codes_df.columns:
            merged_gdf['watercode'] = pd.to_numeric(merged_gdf['watercode'], errors='coerce').fillna(-1).astype(int)
            
            # Hotfix: Map Ise Bay sub-codes (201, 202) to the main Ise Bay code (200)
            # Starting in 2013, the raw shapefiles split Ise Bay into these sub-codes, 
            # which are missing from the water_manual.xls.
            merged_gdf['watercode'] = merged_gdf['watercode'].replace({201: 200, 202: 200})
            
            codes_df['watercode'] = pd.to_numeric(codes_df['watercode'], errors='coerce').fillna(-1).astype(int)
            
            merged_gdf = merged_gdf.merge(codes_df, on='watercode', how='left')
    
    return merged_gdf

def clean_and_process_data(gdf):
    """
    Apply standard cleaning and processing:
    1. Detect if v2 parameter alternatives exist (e.g. do_2), and map them back to default aliases (e.g. do_).
    2. Convert 'do_' (Dissolved Oxygen) to numeric.
    3. Add 'season' column based on 'surveymont'.
    4. Ensure geometry is valid.
    """
    print("Processing data (detecting V2 parameters, cleaning DO, adding seasons)...")
    
    # Check for V2 columns and map them
    cols = gdf.columns
    for col in cols:
        base_col = None
        if col.endswith('2') and len(col) > 1:
            base_col = col[:-1]
            # Special case mapping where original may have trailing underscore
            if base_col == 'do' and 'do_' in cols:
                base_col = 'do_'
        elif col == 'chloroph_1' and 'chlorophyl' in cols:
            base_col = 'chlorophyl'
                
        if base_col and base_col in cols:
            if pd.api.types.is_numeric_dtype(gdf[col]):
                base_valid = gdf[base_col].notna().sum()
                v2_valid = gdf[col].notna().sum()
                if v2_valid >= base_valid:
                    gdf[base_col] = gdf[col]
                    print(f"Mapped {col} -> {base_col} ({col}: {v2_valid} valid float entries | {base_col}: {base_valid} valid originally)")

    # Clean DO column (ensure it gets numeric casting)
    if 'do_' in gdf.columns:
        gdf['do_'] = pd.to_numeric(gdf['do_'], errors='coerce')
    
    # Add Season
    if 'surveymont' in gdf.columns:
        gdf['season'] = gdf['surveymont'].apply(get_season)
    
    # Ensure it's a GeoDataFrame
    if not isinstance(gdf, gpd.GeoDataFrame):
        gdf = gpd.GeoDataFrame(gdf, geometry='geometry')
        
    # Optional: Coordinate reference system check (assuming raw data is consistent, usually JGD2000 or WGS84)
    # merged_gdf.crs = ... 
    
    return gdf

def load_and_process_data(force_reload=False, save_to_feather=True):
    """
    Main entry point.
    1. Checks if processed Feather file exists.
    2. If exists and not force_reload, loads it.
    3. Otherwise, loads raw data, processes it, and saves to Feather.
    """
    feather_path = ProjectPaths.MERGED_DATA_FILE
    
    if feather_path.exists() and not force_reload:
        print(f"Loading processed data from {feather_path}...")
        try:
            return gpd.read_feather(feather_path)
        except Exception as e:
            print(f"Failed to read Feather file: {e}. Reloading from raw source.")
    
    # Reload from raw
    raw_gdf = load_raw_shapefiles()
    processed_gdf = clean_and_process_data(raw_gdf)
    
    if save_to_feather:
        print(f"Saving processed data to {feather_path}...")
        try:
            processed_gdf.to_feather(feather_path)
        except Exception as e:
            print(f"Warning: Failed to save Feather file: {e}")
            
    return processed_gdf

if __name__ == "__main__":
    # Test run
    df = load_and_process_data(force_reload=False) # Default to loading existing to test path
    print(f"Loaded data with shape: {df.shape}")
    print(df.head())

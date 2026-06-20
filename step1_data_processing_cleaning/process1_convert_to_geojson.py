
import geopandas as gpd
import pandas as pd
import argparse
import sys
"""
Script to convert spatial data files (CSV, Feather, Shapefile, etc.) to GeoJSON format.
This is useful for visualizing data in VS Code using the 'Geo Data Viewer' extension.

Usage:
    python scripts/convert_to_geojson.py <input_file> [options]

Arguments:
    input_file          Name or path of the file to convert (searches in current dir, data/processed, data/raw).
    --output, -o        Optional custom output path for the .geojson file.

Examples:
    python scripts/convert_to_geojson.py merged_gdf.feather
    python scripts/convert_to_geojson.py my_data.csv
    python scripts/convert_to_geojson.py data/raw/survey.shp -o final_map.geojson

Requirements:
    - geopandas
    - pandas
    - shapely (for CSV geometry)
"""

from pathlib import Path


# Add project root to path so we can import 'scripts' if run directly
current_dir = Path(__file__).resolve().parent
if str(current_dir.parent) not in sys.path:
    sys.path.append(str(current_dir.parent))

try:
    from utils.paths import ProjectPaths
except ImportError:
    # If run as a module or paths.py is local
    try:
        from utils.paths import ProjectPaths
    except ImportError:
        print("Could not import ProjectPaths. Please ensure you are running from the project root.")
        sys.exit(1)

def detect_geometry_columns(df):
    """Attempt to find latitude and longitude columns."""
    cols = [c.lower() for c in df.columns]
    
    lat_col = next((c for c in df.columns if c.lower() in ['lat', 'latitude', 'y']), None)
    lon_col = next((c for c in df.columns if c.lower() in ['lon', 'long', 'longitude', 'x']), None)
    
    return lat_col, lon_col

def load_file(file_path: Path):
    """
    Load a file (csv, feather, shp, etc.) into a GeoDataFrame.
    """
    print(f"Reading {file_path}...")
    ext = file_path.suffix.lower()
    
    if ext == '.feather':
        try:
            return gpd.read_feather(file_path)
        except Exception:
            # Fallback to pandas read_feather then convert if not a GDF
            df = pd.read_feather(file_path)
            # If it's just a DataFrame, we need geometry
            if 'geometry' not in df.columns:
                print("Feather file does not contain a 'geometry' column.")
                lat, lon = detect_geometry_columns(df)
                if lat and lon:
                    print(f"Detected coordinates: {lat}, {lon}")
                    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")
                else:
                    raise ValueError("Could not detect geometry or lat/lon columns in Feather file.")
            return gpd.GeoDataFrame(df, geometry='geometry')

    elif ext == '.csv':
        df = pd.read_csv(file_path)
        
        # Check for WKT
        if 'geometry' in df.columns:
            from shapely import wkt
            try:
                df['geometry'] = df['geometry'].apply(wkt.loads)
                return gpd.GeoDataFrame(df, geometry='geometry')
            except Exception:
                pass # WKT parse failed, try lat/lon
        
        lat, lon = detect_geometry_columns(df)
        if lat and lon:
            print(f"Detected coordinates: {lat}, {lon}")
            return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")
        else:
            raise ValueError("Could not detect 'geometry' column or valid Lat/Lon columns in CSV.")
            
    else:
        # Try standard geopandas reading (shp, geojson, gpkg, etc.)
        return gpd.read_file(file_path)

def resolve_path(filename: str):
    """
    Search for the file in logical locations:
    1. Exact path provided
    2. processed data dir
    3. raw data dir
    """
    path = Path(filename)
    if path.exists():
        return path
    
    # Check processed
    p_path = ProjectPaths.PROCESSED_DATA_DIR / filename
    if p_path.exists():
        return p_path
        
    # Check raw
    r_path = ProjectPaths.RAW_DATA_DIR / filename
    if r_path.exists():
        return r_path
        
    return None

def convert_to_geojson(input_filename: str, output_filename: str = None):
    """
    Convert a generic file to GeoJSON.
    """
    input_path = resolve_path(input_filename)
    
    if not input_path:
        print(f"Error: File '{input_filename}' not found.")
        print(f"Searched in:\n- {Path(input_filename).absolute()}\n- {ProjectPaths.PROCESSED_DATA_DIR}\n- {ProjectPaths.RAW_DATA_DIR}")
        return

    try:
        gdf = load_file(input_path)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    # Determine Output Path
    if output_filename:
        out_path = Path(output_filename)
    else:
        # Default to processed directory if just a clean name, or side-by-side
        if input_path.parent == ProjectPaths.PROCESSED_DATA_DIR:
             out_path = input_path.with_suffix('.geojson')
        elif input_path.parent == ProjectPaths.RAW_DATA_DIR:
             # Don't pollute raw dir, save to processed
             out_path = ProjectPaths.PROCESSED_DATA_DIR / (input_path.stem + ".geojson")
        else:
             out_path = input_path.with_suffix('.geojson')

    print(f"Converting to GeoJSON: {out_path}")
    
    try:
        # timestamp handling for GeoJSON compatibility
        for col in gdf.select_dtypes(include=['datetime64']).columns:
            gdf[col] = gdf[col].astype(str)
            
        gdf.to_file(out_path, driver='GeoJSON')
        print(f"Success! GeoJSON saved to: {out_path}")
        print("You can right-click this file in VS Code and select 'View Map'.")
    except Exception as e:
        print(f"Error saving GeoJSON: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert spatial data (CSV, Feather, SHP) to GeoJSON.")
    parser.add_argument("input_file", help="Path or name of the file to convert.")
    parser.add_argument("--output", "-o", help="Optional output path for the GeoJSON file.", default=None)
    
    args = parser.parse_args()
    
    convert_to_geojson(args.input_file, args.output)

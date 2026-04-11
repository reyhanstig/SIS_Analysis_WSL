import hashlib
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import geopandas as gpd

from paths import ProjectPaths

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def get_md5(file_path: Path) -> str:
    """Calculate the MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def main():
    zip_dir = ProjectPaths.DATA_DIR / "zip"
    if not zip_dir.exists():
        logging.error(f"Zip directory {zip_dir} does not exist.")
        return

    raw_dir = ProjectPaths.RAW_DATA_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)

    seen_hashes = set()
    
    # Load water_manual mapping
    water_mapping = {}
    xls_path = ProjectPaths.WATER_MANUAL_PATH
    if xls_path.exists():
        try:
            df_manual = pd.read_excel(xls_path, sheet_name='3. Water mass code', header=3)
            df_manual = df_manual.rename(columns={
                'Water Mass Code': 'watercode',
                'Water Mass Name': 'watermass_name'
            })
            
            if 'watercode' in df_manual.columns and 'watermass_name' in df_manual.columns:
                for _, m_row in df_manual.dropna(subset=['watercode', 'watermass_name']).iterrows():
                    c_val = str(m_row['watercode']).split('.')[0]
                    n_val = str(m_row['watermass_name'])
                    
                    # Hardcoded overrides as requested
                    if c_val in ['201', '202'] or '伊勢' in n_val or 'ise' in n_val.lower():
                        water_mapping[c_val] = 'Ise'
                    elif '東京' in n_val or 'tokyo' in n_val.lower():
                        water_mapping[c_val] = 'Tokyo'
                    else:
                        water_mapping[c_val] = n_val
                        
            # Ensure 201 and 202 are mapped even if not in XLS
            water_mapping['201'] = 'Ise'
            water_mapping['202'] = 'Ise'
        except Exception as e:
            logging.error(f"Failed to load water_manual.xls mappings: {e}")
    else:
        logging.warning(f"Water manual not found at {xls_path}. Using extracted text where possible.")
    
    zip_files = list(zip_dir.glob("*.zip"))
    logging.info(f"Found {len(zip_files)} zip files in {zip_dir}.")

    for zip_path in zip_files:
        file_hash = get_md5(zip_path)
        if file_hash in seen_hashes:
            logging.info(f"Skipping duplicate zip file (hash match): {zip_path.name}")
            continue
        
        seen_hashes.add(file_hash)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(temp_path)
            except zipfile.BadZipFile:
                logging.error(f"Bad zip file: {zip_path.name}")
                continue

            shp_files = list(temp_path.rglob("*.shp"))
            if not shp_files:
                logging.warning(f"No .shp file found in {zip_path.name}. Skipping.")
                continue

            # Load metadata
            shp_path = shp_files[0]
            try:
                gdf = gpd.read_file(shp_path, encoding='shift-jis')
            except Exception as e:
                logging.error(f"Failed to read {shp_path.name} in {zip_path.name}: {e}")
                continue
                
            if gdf.empty:
                logging.warning(f"Shapefile {shp_path.name} in {zip_path.name} is empty.")
                continue

            # First row
            row = gdf.iloc[0]
            
            # Requirement: Print gdf.columns to verify exact string to use for Region
            logging.info(f"[{zip_path.name}] Columns available: {list(gdf.columns)}")
            
            # Determine Year
            if 'nendo' not in gdf.columns:
                logging.warning(f"'nendo' column missing in {zip_path.name}. Cannot determine year. Skipping.")
                continue
            year = row['nendo']

            # Determine Water Mass
            if 'watercode' not in gdf.columns:
                logging.error(f"'watercode' column missing in {zip_path.name}. Cannot determine water mass.")
                continue
                
            code_val = str(row['watercode']).split('.')[0]
            
            # Use water_mapping to find the water mass name
            if code_val in water_mapping:
                region = water_mapping[code_val]
            else:
                # Fallback to the code itself if mapping is missing
                region = f"WaterMass{code_val}"
                logging.warning(f"Could not find mapping for watercode {code_val} in {zip_path.name}. Using fallback {region}.")
            
            # Format Folder Name
            folder_name = f"{year}_{region}_wq-raw".replace(" ", "_")
            target_folder = raw_dir / folder_name

            if target_folder.exists():
                logging.info(f"Target folder {folder_name} already exists (second duplicate check). Skipping extraction for {zip_path.name}.")
                continue

            # Create target folder out of the temporary location
            target_folder.mkdir(parents=True, exist_ok=True)
            
            # Move all extracted contents to target folder
            # Keep in mind some zips extract a single folder, others extract many files.
            # We want whatever is in the root of the temp dir to go into the target folder.
            for item in temp_path.iterdir():
                shutil.move(str(item), str(target_folder))
            
            logging.info(f"Successfully processed {zip_path.name} -> {target_folder}")

if __name__ == "__main__":
    main()

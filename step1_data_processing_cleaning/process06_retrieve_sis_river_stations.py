#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))



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
"""
Retrieve and store river water level & flow rate stations within the bounds of the Seto Inland Sea.
Uses Selenium to bypass database access blocks and GeoPandas for spatial filtering.
"""

import sys
import os
import re
import time
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

# Define Prefectures surrounding the Seto Inland Sea to filter search results early
SIS_PREFECTURES = [
    '兵庫県', '岡山県', '広島県', '山口県', '徳島県',
    '香川県', '愛媛県', '福岡県', '大分県', '大阪府', '和歌山県'
]

def create_driver():
    """Initialize headless Chrome Selenium driver."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=options)

def dms_str_to_dd(dms_str):
    """Convert DMS-encoded string (e.g. '0344833000') to decimal degrees."""
    dms_str = dms_str.zfill(10)
    deg = int(dms_str[:3])
    min_ = int(dms_str[3:5])
    sec = float(dms_str[5:7] + '.' + dms_str[7:])
    return deg + (min_ / 60.0) + (sec / 3600.0)

def get_all_station_ids(driver, komoku='02'):
    """Retrieve all station IDs and names for the given observation code across Japan."""
    stations = []
    page = 0
    print("Scraping station list pages from MLIT database...")
    
    while True:
        url = f'http://www1.river.go.jp/cgi-bin/SrchSite.exe?KOMOKU={komoku}&NAME=&SUIKEI=-00001&KASEN=&KEN=-1&CITY=&PAGE={page}'
        driver.get(url)
        time.sleep(1.5)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Locate search results table
        data_table = None
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if len(rows) > 2:
                first_cells = [c.get_text(strip=True) for c in rows[0].find_all('td')]
                if 'No' in first_cells and '項目' in first_cells:
                    data_table = table
                    break
        
        if data_table is None:
            break
            
        rows = data_table.find_all('tr')[1:]
        page_stations_count = 0
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 6:
                continue
            
            link = row.find('a', href=re.compile(r"SiteDetail1"))
            if link:
                match = re.search(r"'(\d+)'", link.get('href'))
                if match:
                    stations.append({
                        'station_id': match.group(1),
                        'item': cells[1].get_text(strip=True),
                        'river_system': cells[2].get_text(strip=True),
                        'river_name': cells[3].get_text(strip=True),
                        'station_name': cells[4].get_text(strip=True),
                        'location': cells[5].get_text(strip=True),
                    })
                    page_stations_count += 1
        
        if page_stations_count == 0:
            break
            
        # Check if Next button exists
        next_btn = soup.find('img', src=re.compile(r'next\.gif'))
        if not next_btn:
            break
            
        page += 1
        
    print(f"Retrieved {len(stations)} stations nationwide.")
    return stations

def scrape_coordinates(driver, station_id):
    """Scrape coordinates from details page and return (lat, lon)."""
    try:
        url = f'http://www1.river.go.jp/cgi-bin/SiteInfo.exe?ID={station_id}'
        driver.get(url)
        time.sleep(1.0)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        map_link = soup.find('a', href=re.compile(r'DspMapPosition'))
        if map_link:
            href = map_link.get('href')
            sido_match = re.search(r'SIDO=(\d+)', href)
            skeido_match = re.search(r'SKEIDO=(\d+)', href)
            if sido_match and skeido_match:
                lat = dms_str_to_dd(sido_match.group(1))
                lon = dms_str_to_dd(skeido_match.group(1))
                return lat, lon
    except Exception as e:
        print(f"  Error loading details for station {station_id}: {e}")
    return None, None

def main():
    ProjectPaths.ensure_directories()
    output_file = PROCESSED_DATA_DIR / 'sis_river_water_stations.csv'
    
    driver = create_driver()
    try:
        # Step 1: Scrape all stations nationwide
        all_stations = get_all_station_ids(driver, komoku='02')
        
        # Step 2: Filter by prefecture to save scraping time
        sis_prefecture_stations = [
            stn for stn in all_stations 
            if any(pref in stn['location'] for pref in SIS_PREFECTURES)
        ]
        print(f"Filtered to {len(sis_prefecture_stations)} stations in Seto Inland Sea prefectures.")
        
        # Step 3: Scrape coordinates for filtered stations
        scraped_data = []
        total = len(sis_prefecture_stations)
        
        for idx, stn in enumerate(sis_prefecture_stations):
            print(f"Scraping coordinates {idx+1}/{total}: {stn['station_name']} ({stn['station_id']})...")
            lat, lon = scrape_coordinates(driver, stn['station_id'])
            if lat and lon:
                stn['latitude'] = lat
                stn['longitude'] = lon
                scraped_data.append(stn)
            else:
                print(f"  Failed to retrieve coordinates for {stn['station_name']}")
                
        df = pd.DataFrame(scraped_data)
        
        # Step 4: Spatial intersection check with the Seto Inland Sea shapefile
        land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary_2.shp"
        
        if land_boundary_path.exists() and not df.empty:
            print("Performing spatial boundary filtering using Setonaikai_boundary_2.shp...")
            sis_land = gpd.read_file(land_boundary_path)
            if sis_land.crs != 'EPSG:4326':
                sis_land = sis_land.to_crs('EPSG:4326')
                
            gdf = gpd.GeoDataFrame(
                df,
                geometry=gpd.points_from_xy(df['longitude'], df['latitude']),
                crs='EPSG:4326'
            )
            
            # spatial join to filter only points falling within the shapefile polygons
            gdf_filtered = gpd.sjoin(gdf, sis_land, how='inner', predicate='within')
            
            # Clean up shapefile columns from join
            df_filtered = pd.DataFrame(gdf_filtered.drop(columns=['geometry', 'index_right']))
            print(f"Retained {len(df_filtered)} stations strictly within Seto Inland Sea boundary.")
        else:
            # Fallback to coordinate bounding box [130.5, 135.5, 33.0, 35.0] if shapefile doesn't exist
            print("Shapefile not found. Falling back to rectangular bounding box filter.")
            df_filtered = df[
                (df['longitude'] >= 130.5) & (df['longitude'] <= 135.5) &
                (df['latitude'] >= 33.0) & (df['latitude'] <= 35.0)
            ].copy()
            print(f"Retained {len(df_filtered)} stations inside rectangular bounds.")
            
        # Step 5: Save results
        df_filtered.to_csv(output_file, index=False)
        print(f"Successfully stored filtered stations to {output_file}")
        
    finally:
        driver.quit()

if __name__ == '__main__':
    main()

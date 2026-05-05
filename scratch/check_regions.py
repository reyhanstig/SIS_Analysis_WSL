import pandas as pd
import geopandas as gpd

gdf = gpd.read_feather('/home/reyha/SIS_Analysis_WSL/data/processed/merged_gdf.feather')
print(gdf['watermass_name'].unique())
if 'division' in gdf.columns:
    print(gdf['division'].unique())

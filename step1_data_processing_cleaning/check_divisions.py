import pandas as pd
from pathlib import Path
import sys
import geopandas as gpd

sys.path.append(str(Path.cwd() / 'scripts'))
from utils.paths import ProjectPaths

env_data_path = ProjectPaths.PROCESSED_DATA_DIR / 'merged_gdf_saisuipoin_cleaned.feather'
env_data_df = pd.read_feather(env_data_path)
print(env_data_df['division'].unique())
print(len(env_data_df['division'].unique()))

divisions = env_data_df[['zettaicode', 'division']].drop_duplicates()
print(len(divisions['zettaicode'].unique()), len(divisions))

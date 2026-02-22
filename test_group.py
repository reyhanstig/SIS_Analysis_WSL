import pandas as pd
from scripts.paths import ProjectPaths

merged_gdf = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)

print("Total years in merged_gdf before anything:", sorted(list(merged_gdf['year'].unique())))

subset = merged_gdf[
    (merged_gdf['season'] == 'Summer') & 
    (merged_gdf['saisuipoin'] == 2)
].dropna(subset=['do_']).copy()

print("Total years in subset after filter & dropna:", sorted(list(subset['year'].unique())))

subset['do_'] = pd.to_numeric(subset['do_'], errors='coerce')

yd = subset.groupby(['zettaicode', 'year'])['do_'].mean()

print("Years after groupby mean:", sorted(list(yd.index.get_level_values('year').unique())))

yearly_do = yd.unstack('year')

print("Years after unstack:", list(yearly_do.columns))

# Drop stations below min_periods threshold
filtered_do = yearly_do[yearly_do.notna().sum(axis=1) >= 15]

print("Years after filtering stations:", list(filtered_do.columns))


import pandas as pd
import numpy as np
from pathlib import Path

df_08 = pd.read_csv('data/processed/stations_decorrelation_scale.csv')
df_08['Station_ID'] = df_08['Station_ID'].astype(str).str.zfill(8)

files_40 = Path('data/processed/step2_decorrelation_scale_analysis/40_calculate_decorrelation_scale_per_bay/').glob('*.csv')
df_40_list = [pd.read_csv(f) for f in files_40]
df_40 = pd.concat(df_40_list)
df_40['Station_ID'] = df_40['Station_ID'].astype(str).str.zfill(8)

common_stations = set(df_08['Station_ID']).intersection(set(df_40['Station_ID']))
print(f"Number of common stations between 08 and 40: {len(common_stations)}")

diffs = []
for st in common_stations:
    v08 = df_08[df_08['Station_ID'] == st]['Decorrelation_Scale_km'].values[0]
    # some stations might not be in 40 if they aren't in a named bay?
    if st in df_40['Station_ID'].values:
        v40 = df_40[df_40['Station_ID'] == st]['Decorrelation_Scale_km'].values[0]
        if abs(v08 - v40) > 0.001:
            diffs.append((st, v08, v40))

print(f"Number of stations with differences > 0.001: {len(diffs)}")
if diffs:
    print("Example differences (Station_ID, v08, v40):")
    for d in diffs[:5]:
        print(d)


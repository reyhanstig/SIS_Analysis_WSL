import pandas as pd
import numpy as np

df_08 = pd.read_csv('data/processed/stations_decorrelation_scale.csv')
df_10 = pd.read_csv('data/processed/step2_decorrelation_scale_analysis/10_calculate_bay_decorrelation_scales/seto_inland_sea_decorrelation_scale.csv')

print(f"df_08 columns: {df_08.columns}")
print(f"df_10 columns: {df_10.columns}")

df_08['Station_ID'] = df_08['Station_ID'].astype(str).str.zfill(8)
df_10['Station_ID'] = df_10['Station_ID'].astype(str).str.zfill(8)

common_stations = set(df_08['Station_ID']).intersection(set(df_10['Station_ID']))
print(f"Number of common stations: {len(common_stations)}")

diffs = []
for st in common_stations:
    v08 = df_08[df_08['Station_ID'] == st]['Decorrelation_Scale_km'].values[0]
    v10 = df_10[df_10['Station_ID'] == st]['Decorrelation_Scale_km'].values[0]
    
    # Also get A_fit and B_fit
    A08 = df_08[df_08['Station_ID'] == st]['Amplitude_A'].values[0]
    A10 = df_10[df_10['Station_ID'] == st]['Amplitude_A'].values[0]
    
    n08 = df_08[df_08['Station_ID'] == st]['n_neighbors_100km'].values[0]
    n10 = df_10[df_10['Station_ID'] == st]['n_neighbors_100km'].values[0]

    if abs(v08 - v10) > 0.001:
        diffs.append((st, v08, v10, A08, A10, n08, n10))

print(f"Number of stations with differences > 0.001: {len(diffs)}")
if diffs:
    print("Example differences (Station_ID, v08, v10, A08, A10, n08, n10):")
    for d in diffs[:10]:
        print(d)

# Bathymetry Evaluation: GEBCO vs JODC

This report summarizes the findings from analyzing the available GEBCO and JODC bathymetry datasets in the workspace to determine the most appropriate data source for the Seto Inland Sea / Osaka Bay spatial interpolation.

## 1. GEBCO (Global Earth Bathymetric Chart of the Oceans)
- **Source File:** `data/raw/GEBCO_10_Mar_2026_d2286085bd59/gebco_2025_...nc`
- **Format:** NetCDF (gridded).
- **Coverage:** Bounding box Lon(129.86, 136.18), Lat(32.33, 35.11).
- **Resolution:** 15 arc-second (approx. 0.004167 degrees, or ~460m).
- **Total Points:** 1,013,356 grid cells.
- **Depth Range:** -1843.00m to 6416.00m (includes both above-sea-level elevation and deep ocean depth).
- **Advantages:** 
  - Uniform, regular grid makes it ideal for immediate use in spatial interpolation algorithms (like Kriging or Inverse Distance Weighting).
  - Native NetCDF format is highly optimized for Python with `xarray`.
- **Disadvantages:** 
  - Contains land elevation, which requires explicit masking against shoreline boundaries to isolate marine environments.

## 2. JODC (Japan Oceanographic Data Center)
- **Source Files:** `data/raw/JODC_mesh500_SIS/mesh500_*.txt`
- **Format:** Point samples in space-separated text files.
- **Coverage:** Bounding box Lon(130.00, 136.00), Lat(32.00, 35.00).
- **Resolution:** 500m mesh.
- **Total Water Points:** 105,057 discrete points.
- **Depth Range:** 1.00m to 1929.00m.
- **Advantages:**
  - Highly tailored for Japanese coastal waters.
  - Contains a discrete `type` flag where `type == 1` specifically denotes valid marine water points, inherently acting as a land mask.
- **Disadvantages:**
  - The data is provided as scattered point samples (GeoDataFrame/Pandas) rather than a uniform grid, requiring rasterization before it can be used efficiently as a background drift/constraint matrix for Kriging.

## Recommendation
For the `51_osaka_bay_hypoxia_benthos_v2.ipynb` spatial interpolation, **GEBCO is the recommended primary bathymetry source**. The uniform grid (NetCDF) naturally aligns with the requirements of grid-based interpolation like Kriging. The land boundary can easily be masked using the existing high-resolution Setonaikai Prefecture shapefile (`ProjectPaths.BOUNDARIES_DIR`).

*Note: JODC can be used as a secondary validation layer or to explicitly filter out coastal grid cells if the shapefile masking proves insufficient.*

## Quick context

This repository contains data processing and analysis notebooks for Seto Inland Sea water quality. Primary artifacts:
- `notebooks/` — Jupyter notebooks (main working area).
- `data/raw/`, `data/processed/` — raw and processed datasets; `data/boundaries/` contains shapefiles (POLYGON.*, POLYLINE.*).
- `requirements.txt` — Python requirements used by the notebooks.

Purpose for an AI coding assistant: help the author quickly debug and extend notebooks and data pipelines. Below are concrete, reproducible patterns and checks used throughout the project.

## Environment & install

- Preferred quick setup (virtualenv):
  - Create: `python -m venv .venv`
  - Activate (PowerShell): `.\.venv\Scripts\Activate.ps1` (PowerShell may block scripts; if blocked, either run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` as admin, or use the batch activate in cmd: `.\.venv\Scripts\activate.bat`).
  - Install deps: `pip install -r requirements.txt` (file at repo root).
- Note: geopandas / cartopy sometimes require system packages. If pip installation fails, prefer conda:
  - `conda create -n sisenv python=3.10 geopandas cartopy pandas matplotlib scipy -y`

## Notebook run conventions

- Notebooks are executed from `notebooks/`. Relative paths assume repo root (e.g. `../data/...`) — confirm with `os.getcwd()` when debugging.
- Typical first cell used in notebooks: install/check requirements or activate environment; if adding an install cell, use `!pip install -r ../requirements.txt` (not recommended for production but common here).

## Data layout & important file types

- Shapefiles: `data/boundaries/.../POLYGON.shp` must be accompanied by `.shx`, `.dbf`, etc. Use `geopandas.read_file(path)` and verify `os.path.exists(path)` before reading.
- Raw environmental data lives under `data/raw/environmental_data/` with per-year folders such as `1999_SIS_wq-raw/`.

## Common column names & processing patterns (use these examples)

- Columns often used in filters and aggregations:
  - `year` — integer year (used to subset time-series)
  - `division` — region name (e.g. `Osaka Bay`)
  - `parameter` — measurement type (e.g. `DO` for dissolved oxygen)
  - `do_` — numeric dissolved oxygen values in some dataframes
  - `surveymont` or `surveymon` / `survey_ym` — month or datetime of sampling (watch for inconsistent names)
  - `saisuipoin` — sampling depth flag (1 = surface, 2 = bottom in some notebooks)

- Safe access pattern (avoid KeyError):
```python
print(df.columns)
if 'year' in df.columns:
    df_year = df[df['year'] == 2022]
else:
    # inspect/derive year from datetime column
    df['year'] = pd.DatetimeIndex(df['survey_ym']).year
```

- Converting numeric columns before aggregation:
```python
df['do_'] = pd.to_numeric(df['do_'], errors='coerce')
grouped = df.groupby(['division','year'])['do_'].mean()
```

## Spatial/variogram patterns to reuse

- Pairwise distances: use `scipy.spatial.distance.pdist` on projected coordinates (or convert lat/lon to meters) rather than Python nested loops for large N.
- Example coordinate extraction for pdist:
```python
coords = np.column_stack((gdf.geometry.x, gdf.geometry.y))
distances = pdist(coords)
```

## Plotting & map extents

- Cartopy is used for map projection. Typical code: 
```python
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent([130.6, 135.6, 32.75, 35.1], crs=ccrs.PlateCarree())
```
Use these extents when plotting Seto Inland Sea maps to match existing figures.

## Debugging gotchas observed in this repo

- Missing columns: many notebook errors are `KeyError` for `'year'`, `'division'`, or `'name'`. Always print `df.columns` and `df.head()` when encountering these.
- Shapefile path problems: check for unicode or trailing spaces in folder names; use `os.listdir()` to inspect actual filenames. Example path used in notebooks: `../data/boundaries/SIS water mass polygon/POLYGON.shp`.
- PowerShell activation: `Activate.ps1` failures due to execution policy — see Environment section.
- Aggregation errors: `TypeError: agg function failed [how->mean,dtype->object]` — typically solved by `pd.to_numeric(..., errors='coerce')` on the column being averaged.

## Where to look first when asked to modify behavior

1. `notebooks/analysis5.ipynb` — active analysis notebook (start here for current work).
2. `README.md` and `requirements.txt` — environment and high-level setup.
3. `data/boundaries/` and `data/raw/` — shape and sample data.

## Examples of targeted prompts you can follow

- "Add a safety check before calling `gpd.read_file()` that verifies the `.shp` and `.dbf` exist and prints the full resolved path."
- "Convert the `do_` column to numeric across all notebooks and add a one-time cleaning cell that logs how many values were coerced to NaN."

## Minimal priority rules for edits

- Prefer notebook edits to preserve exploratory outputs only when asked. For reusable code, propose a small new `.py` utility (e.g., `scripts/io_helpers.py`) and point where notebooks should import it.
- Keep absolute edits minimal; explain alternatives in a short comment when making changes (for reviewers).

---

If anything here is unclear or you want more examples (e.g., a ready-to-run `scripts/` helper for reading shapefiles), tell me which part to expand and I will update this file.

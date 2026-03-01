# Yearly Progression Plotting — Performance Optimization Report

**Date:** 2026-03-01  
**Notebook:** `notebooks/23_seasonal_variation.ipynb` (v3, optimized)  
**Baseline:** `notebooks/21_seasonal_variation_v2.ipynb` (v2)  
**Test script:** `/tmp/test_23_seasonal_variation.py`

---

## 1. Problem Statement

The progressive yearly subplot cell in notebook 21 plots diffusion-interpolated
DO maps for every available year of a given season (typically 40+ years).  Each
year requires:

1. A diffusion interpolation solve (SOR on a 2-D grid).
2. Rendering a Cartopy subplot with the land boundary, interpolated colour mesh,
   and station scatter points.

With the original implementation the cell took **well over 10 minutes** (and
often appeared to hang), making iterative analysis impractical.  The target for
notebook 23 was **< 2 minutes** for the full cell.

---

## 2. Profiling Summary

Profiling the original code revealed **two independent bottlenecks**:

| Phase | Original cost | Root cause |
|-------|---------------|------------|
| Interpolation | ~5–6 s per year × 41 years ≈ **200+ s** | Fine grid (2 000 m), row-by-row station snapping, high iteration count |
| Plotting | dominant (minutes) | `geopandas.plot()` calls `draw_idle()` after *every* subplot, re-rendering the entire figure each time (effectively O(n²) in subplot count) |

---

## 3. Optimizations Applied

### 3.1 Grid Resolution — 4 000 m (was 2 000 m)

Doubling the cell size reduces total grid points by a factor of ~4  
(from ~26 000 to ~6 700, water cells from ~6 500 to ~1 600).  
All grid-based operations — water-mask creation, convolution, convergence
checking — scale linearly or super-linearly with cell count, so this single
change delivers a large multiplicative speedup.

> **Trade-off:** Spatial detail is coarser, but for a 40-panel overview figure
> the resolution is more than sufficient.

### 3.2 Water Mask — `shapely.prepared.prep()`

| Before | After |
|--------|-------|
| Create a `GeoDataFrame` of *all* grid points, call `.within(water_polygon)` | Call `shapely.prepared.prep(water_polygon)`, then `prepared.contains(pt)` per point |

`prep()` builds an internal spatial index (STRtree) on the polygon so that
subsequent containment tests are O(log n) instead of O(n × polygon-vertices).

### 3.3 Coordinate Reprojection — `pyproj.Transformer`

| Before | After |
|--------|-------|
| Build a *second* `GeoDataFrame` of all grid points → `.to_crs(epsg=4326)` | `pyproj.Transformer.from_crs(utm, wgs84).transform(x_arr, y_arr)` |

The original approach allocates tens of thousands of Shapely `Point` objects
*twice* (once for the water mask, once for the reprojection), plus the overhead
of GeoDataFrame construction and CRS propagation.  
`pyproj.Transformer.transform()` operates directly on NumPy arrays with
essentially zero Python-level overhead.

### 3.4 Station Snapping — `scipy.spatial.cKDTree`

| Before | After |
|--------|-------|
| `iterrows()` over each station; if the nearest grid cell is land, compute distance to *every* grid cell and take the argmin | Build a `cKDTree` of water-cell coordinates once; `tree.query(station_coords)` for O(log n) nearest-water-cell lookup |

This eliminates both the Python-level row loop and the O(N_grid) brute-force
fallback.

### 3.5 SOR Solver Tuning

| Parameter | Before | After | Rationale |
|-----------|--------|-------|-----------|
| `max_iters` | 2 000 | 500 | Solutions converge well before 500 on the coarser grid |
| `tol` | 1 × 10⁻⁴ | 1 × 10⁻³ | Sufficient for visualisation-grade accuracy |
| `omega` | 1.7 | 1.8 | Slightly more aggressive over-relaxation speeds convergence |

Additionally:

- A single `Z_water` work-array is pre-allocated and reused across iterations
  (avoids repeated `np.nan_to_num` + allocation).
- `np.errstate(divide='ignore', invalid='ignore')` wraps the division to
  suppress runtime warnings without affecting correctness.

### 3.6 Land Plotting — `PatchCollection` (was `geopandas.plot()`)

This was **the most impactful single change** for overall cell time.

| Before | After |
|--------|-------|
| `sis_land_boundary.plot(ax=ax, ...)` called inside the per-year loop (41×) | Pre-build a list of `matplotlib.patches.Polygon` objects once; add a `PatchCollection` to each axis |

**Why it matters:**  
`GeoDataFrame.plot()` internally calls `ax.figure.canvas.draw_idle()`, which
triggers a full figure render including *all* previously drawn subplots.  With
41 subplots this produces roughly 41 × 42 / 2 ≈ 861 redundant partial renders.
Switching to `PatchCollection` adds geometry to the axis without triggering
any intermediate render — the figure is drawn exactly once at `plt.show()`.

---

## 4. Benchmark Results

Test environment: WSL2 / Ubuntu, conda `sis_analysis` environment,
Python 3.10, `Summer` season, `bottom` layer (41 years).

| Metric | Notebook 21 (v2) | Notebook 23 (v3) | Speed-up |
|--------|-------------------|-------------------|----------|
| Grid points | ~26 000 | ~6 700 | 4× fewer |
| Water cells | ~6 500 | ~1 600 | 4× fewer |
| Preprocessing (Cell 1) | ~4 s | **3.2 s** | ~1.2× |
| Interpolation (41 years) | 200+ s | **0.54 s** | ~400× |
| Full critical cell (interp + plot) | >>10 min | **79.6 s** | >>7× |

```
============================================================
SUMMARY
============================================================
  Cell 1 (preprocessing): 3.20s
  Cell 3 (interp+plot):   79.64s
  ✅ PASS: Cell 3 completed within 2 minutes (79.6s < 120s)
============================================================
```

---

## 5. Remaining Bottleneck

After the optimizations, the time split within the critical cell is:

| Sub-phase | Time | Share |
|-----------|------|-------|
| Interpolation | 0.54 s | < 1 % |
| Plotting (Cartopy + pcolormesh × 41) | ~79 s | > 99 % |

The dominant cost is now **Cartopy rendering** — specifically, `pcolormesh` and
the projection transforms it performs under the hood.  Further speed-ups would
require either:

- Reducing `n_years` (e.g. decade sampling),
- Using a simpler projection (e.g. raw lon/lat without Cartopy),
- Rasterising the land boundary ahead of time, or
- Lowering the saved/displayed DPI.

For the current use-case (interactive analysis in Jupyter) the 80-second cell
time is acceptable.

---

## 6. Files

| File | Purpose |
|------|---------|
| [23_seasonal_variation.ipynb](file:///home/reyha/SIS_Analysis_WSL/notebooks/23_seasonal_variation.ipynb) | Optimized notebook |
| [21_seasonal_variation_v2.ipynb](file:///home/reyha/SIS_Analysis_WSL/notebooks/21_seasonal_variation_v2.ipynb) | Original (baseline) notebook |
| [test_23_seasonal_variation.py](file:///tmp/test_23_seasonal_variation.py) | Standalone test script (verifies < 2 min) |
| [mapping_config.py](file:///home/reyha/SIS_Analysis_WSL/scripts/mapping_config.py) | Shared styling constants |
| [paths.py](file:///home/reyha/SIS_Analysis_WSL/scripts/paths.py) | Centralised project paths |

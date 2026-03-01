# SIS Mapping Standard

This document defines the standardized mapping format for all geospatial visualizations in the Seto Inland Sea (SIS) analysis pipeline. Derived from the final output of `notebooks/pipeline/01_Data_Processing.ipynb`.

**Last Updated:** 2026-02-28

---

## 1. Required Imports

```python
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from scripts.paths import ProjectPaths
from scripts.mapping_config import MappingConfig
```

> [!IMPORTANT]
> Do **not** import `cartopy.feature as cfeature`. The default Cartopy features (`LAND`, `COASTLINE`, `OCEAN`) use low-resolution global datasets that fail to capture the intricate shorelines and narrow straits of the Seto Inland Sea.

---

## 2. Base Figure Setup

```python
fig, ax = plt.subplots(figsize=(10, 8), subplot_kw={'projection': ccrs.PlateCarree()})

# Ocean background — set directly on the axes
ax.set_facecolor(MappingConfig.COLOR_OCEAN)
```

> [!NOTE]
> **Why `set_facecolor` instead of `cfeature.OCEAN`?**
> Cartopy's `cfeature.OCEAN` does not recognize the narrow bodies of water inside the Seto Inland Sea. By setting the entire axis background to `lightblue`, the sea automatically fills all gaps left uncovered by the land polygons.

### 2.1 Multi-Subplot Figure Sizing

When plotting grids of multiple Cartopy subplots, rigid `figsize` definitions will enforce problematic blank padding (vertical whitespace) if the user's fixed `figsize` proportions do not match the geographic `extent` proportions explicitly enforced by Cartopy layout generation. Always define `fig_height` proportionally when working with `.subplots(n_rows, n_cols)`:

```python
extent = [bounds[0]-0.2, bounds[2]+0.2, bounds[1]-0.2, bounds[3]+0.2]
aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])

fig_width = 25 # Set maximum allowed width
width_per_subplot = fig_width / n_cols
height_per_subplot = (width_per_subplot * aspect_ratio) + 0.3 # 0.3 for title buffer
fig_height = height_per_subplot * n_rows

fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height), ...)
```

---

## 3. Custom Coastal Boundaries

The SIS pipeline relies on two distinct boundary files depending on the task: one for computational masking and one for accurate geospatial plotting.

### 3.1. Computational Mask (Water Area)
This file isolates the pure water area of the Seto Inland Sea. Use this to mask land areas during spatial interpolations (Kriging, Diffusion) or to build valid water grids.
```python
water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp"
sis_water_boundary = gpd.read_file(water_boundary_path)
# Often projected to UTM (e.g., EPSG:32653) for meter-based distance/mesh calculations
```

### 3.2. Plotting Mask (Landmass Boundary)
Use the pre-filtered, high-resolution SIS prefecture boundary shapefile to draw intricate coastlines and islands on top of Cartopy maps, instead of using low-resolution `cfeature.LAND`.

```python
land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary.shp"
sis_land_boundary = gpd.read_file(land_boundary_path)

# Enforce WGS84 to match PlateCarree projection
if sis_land_boundary.crs != "EPSG:4326":
    sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")

# Plot land masses
sis_land_boundary.plot(
    ax=ax,
    facecolor=MappingConfig.COLOR_LAND,
    edgecolor=MappingConfig.COLOR_LAND_EDGE,
    linewidth=MappingConfig.LINEWIDTH_LAND,
    transform=ccrs.PlateCarree(),
    zorder=MappingConfig.ZORDER_LAND
)
```


---

## 4. Gridlines

```python
gl = ax.gridlines(draw_labels=True, linestyle=MappingConfig.GRID_LINESTYLE, 
                  color=MappingConfig.GRID_COLOR, alpha=MappingConfig.GRID_ALPHA, 
                  linewidth=MappingConfig.GRID_LINEWIDTH, zorder=MappingConfig.ZORDER_GRIDLINES)
gl.top_labels = False
gl.right_labels = False
```

---

## 5. Map Extent

Dynamically crop to the dataset being visualized, with a 0.2° buffer:

```python
bounds = data_gdf.total_bounds  # [minx, miny, maxx, maxy]
ax.set_extent([
    bounds[0] - 0.2,  # xmin
    bounds[2] + 0.2,  # xmax
    bounds[1] - 0.2,  # ymin
    bounds[3] + 0.2   # ymax
], crs=ccrs.PlateCarree())
```

---

## 6. Z-Order Management

| Z-Order | Config Variable | Layer                                      |
| :------ | :---------------------------------- | :----------------------------------------- |
| base    | `ZORDER_OCEAN` | Ocean background (`set_facecolor`)         |
| 1       | `ZORDER_LAND` | Land masses (SIS prefecture shapefile)     |
| 2       | `ZORDER_GRIDLINES` | Gridlines                                  |
| 3       | `ZORDER_PREDICTED` | Data overlays (scatter, contours, etc.)    |
| 5      | `ZORDER_OBSERVATIONS`| Annotations, text labels, direct observations |

---

## 7. Variable-Specific Configurations

Use `MappingConfig.get_var_settings(variable_name)` to dynamically pull standardized `vmin`, `vmax`, `cmap`, and label definitions.

```python
# Fetch mapping configuration for specific variables
var_cfg = MappingConfig.get_var_settings('do_')
cmap = var_cfg['cmap']          # e.g., 'jet_r' for dissolved oxygen
vmin = var_cfg['vmin']          # e.g., 0.0
vmax = var_cfg['vmax']          # e.g., 12.0
label = var_cfg['label']
```

---

## 8. Complete Minimal Example

```python
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from scripts.paths import ProjectPaths

fig, ax = plt.subplots(figsize=(10, 8), subplot_kw={'projection': ccrs.PlateCarree()})
ax.set_facecolor('lightblue')

# Load Computational Water Mask to get Extents
water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp"
sis_water_boundary = gpd.read_file(water_boundary_path)
if sis_water_boundary.crs != "EPSG:4326":
    sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
bounds = sis_water_boundary.total_bounds

# Load and Plot Landmass Mask
land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary.shp"
sis_land_boundary = gpd.read_file(land_boundary_path)
if sis_land_boundary.crs != "EPSG:4326":
    sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")
sis_land_boundary.plot(ax=ax, facecolor=MappingConfig.COLOR_LAND, edgecolor=MappingConfig.COLOR_LAND_EDGE, 
                  linewidth=MappingConfig.LINEWIDTH_LAND, transform=ccrs.PlateCarree(), 
                  zorder=MappingConfig.ZORDER_LAND)

# Gridlines
gl = ax.gridlines(draw_labels=True, linestyle=MappingConfig.GRID_LINESTYLE, color=MappingConfig.GRID_COLOR, 
                  alpha=MappingConfig.GRID_ALPHA, linewidth=MappingConfig.GRID_LINEWIDTH, 
                  zorder=MappingConfig.ZORDER_GRIDLINES)
gl.top_labels = False
gl.right_labels = False

# Fetch Target Variable Settings
var_cfg = MappingConfig.get_var_settings('do_')

# Data
data_gdf.plot(ax=ax, markersize=3, color='red', alpha=0.8,
              transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_PREDICTED,
               cmap=var_cfg['cmap'], vmin=var_cfg['vmin'], vmax=var_cfg['vmax'])

# Extent (using the water bounds)
ax.set_extent([bounds[0]-0.2, bounds[2]+0.2, bounds[1]-0.2, bounds[3]+0.2],
              crs=ccrs.PlateCarree())

plt.tight_layout()
plt.show()
```

---

## 9. Projection Notes

### Visualization Projection (`ccrs.PlateCarree`)
`PlateCarree` (EPSG:4326) maps longitude and latitude as equal-spaced Cartesian axes. At ~34.5°N, this introduces a ~20% horizontal stretch because 1° longitude ≈ 91 km while 1° latitude ≈ 111 km. This is acceptable for quick inspection plots but does slightly distort the shape of the Seto Inland Sea.

### Analysis Projection (`EPSG:32653 — UTM Zone 53N`)
All quantitative spatial calculations (e.g., the station distance matrix in `08_Decorrelation_Analysis_v3.ipynb`) use **UTM Zone 53N**, which is a meter-based Cartesian system optimized for the Japan region. This guarantees mathematically accurate Euclidean distances in kilometers. The visual projection choice does **not** affect any scientific results.

> [!TIP]
> If true-to-life proportions are needed in a figure (e.g., for publication), switch the axis projection to `ccrs.Mercator()` or `ccrs.UTM(zone=53)`. All other standard elements (boundary file, facecolor, zorder) remain unchanged.

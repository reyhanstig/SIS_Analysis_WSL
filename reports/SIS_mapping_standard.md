# SIS Mapping Standard

This document defines the standardized mapping format for all geospatial visualizations in the Seto Inland Sea (SIS) analysis pipeline. Derived from the final output of `notebooks/pipeline/01_Data_Processing.ipynb`.

**Last Updated:** 2026-02-28

---

## 0. Global Plot Styling

To ensure consistency in font sizes, bold titles, and general aesthetics across all notebooks and scripts, we use a centralized Matplotlib style file located in the project root: `project_style.mplstyle`.

### Usage
In any notebook or script, add this line after your imports:
```python
import matplotlib.pyplot as plt
plt.style.use('../project_style.mplstyle') # Adjust path if necessary
```

### Key Parameters
The style file currently enforces:
- **Title**: Bold, Size 20
- **Axis Labels**: Size 18
- **Tick Labels**: Size 16
- **Legend**: Size 12
- **Global Base Font**: Size 16 (controls scatter labels and annotations)

---

## 1. Required Imports

```python
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from scripts.paths import ProjectPaths
from scripts.mapping_config import MappingConfig

# Apply the global project style
plt.style.use('../project_style.mplstyle')
```

> [!NOTE]
> We now actively use `cfeature.LAND` and `cfeature.COASTLINE` under the main SIS Prefecture Shapefile to fill in large external landmasses outside the detailed region, using explicitly defined Z-Orders to ensure proper layering.

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

When plotting grids of multiple Cartopy subplots, rigid `figsize` definitions will enforce problematic blank padding (vertical, horizontal whitespace) if the user's fixed `figsize` proportions do not match the geographic `extent` proportions explicitly enforced by Cartopy layout generation. Cartopy enforces strict aspect ratios, meaning that if the figure dimensions are slightly off, Cartopy will aggressively shrink the subplot to fit, resulting in huge empty spaces.

Furthermore, `plt.tight_layout()` often struggles with Cartopy axes and spanning colorbars, causing more unexpected shrinking.

Always define `fig_height` proportionally when working with `.subplots(n_rows, n_cols)`, define a dedicated colorbar axis, and use `plt.subplots_adjust()` instead of `tight_layout()`:

```python
extent = [bounds[0]+0.1, bounds[2]+0.1, bounds[1]-0, bounds[3]+0.2]
aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])

fig_width = 25 # Set maximum allowed width
width_per_subplot = fig_width / n_cols
height_per_subplot = (width_per_subplot * aspect_ratio) + 0.3 # Buffer for titles
# Add extra height buffer (e.g. 1.5) for the colorbar at the bottom
fig_height = (height_per_subplot * n_rows) + 1.5 

fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})

# ... plotting logic for each ax ...

# CRITICAL: Adjust the grid explicitly instead of tight_layout()
plt.subplots_adjust(bottom=0.15, wspace=0.05, hspace=0.15)

# Add a dedicated colorbar axes [left, bottom, width, height]
# This prevents the colorbar from stealing horizontal width from the plotting axes
cbar_ax = fig.add_axes([0.25, 0.05, 0.5, 0.03]) 
cbar = fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
```

---

## 3. Custom Coastal Boundaries

The SIS pipeline relies on two distinct boundary files depending on the task: one for computational masking and one for accurate geospatial plotting.

### 3.1. Computational Mask (Water Area)
This file isolates the pure water area of the Seto Inland Sea. Use this to mask land areas during spatial interpolations (Kriging, Diffusion) or to build valid water grids. For regional analyses, there are also dedicated masks available for specific bays, such as Tokyo Bay (`sea_area_mask_Tokyo.shp`) and Ise-Mikawa Bay (`sea_area_mask_Ise.shp`).
```python
water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_sis_simplified.shp"
sis_water_boundary = gpd.read_file(water_boundary_path)
# Often projected to UTM (e.g., EPSG:32653) for meter-based distance/mesh calculations
```

### 3.2. Plotting Mask (Landmass Boundary)
Use the pre-filtered, high-resolution SIS prefecture boundary shapefile or the simplified nation-wide prefectural boundary shapefile to draw intricate coastlines and islands on top of Cartopy maps, instead of using low-resolution `cfeature.LAND`.

For national or multi-region plotting, the pipeline provides a simplified nation-wide prefectural boundary:
- **Path:** `data/boundaries/Whole nation administrative boundary/N03-20240101_prefecture(simplified0.01).shp`
- **CRS:** `EPSG:6668` (reprojected to `EPSG:4326` or coordinate system matching visual mapping)
- **Features:** Simplified to 1% of the original size (14.8 MB vs 178 MB) to optimize plotting speed while retaining high-fidelity coastal outlines.

```python
# Dynamic Landmass Boundary Selection
land_boundary_file = MappingConfig.get_boundary_file(MappingConfig.TARGET_REGION) # e.g., 'Japan', 'Seto Inland Sea', etc.
land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / land_boundary_file
sis_land_boundary = gpd.read_file(land_boundary_path)

# Enforce WGS84 to match PlateCarree projection
if sis_land_boundary.crs != "EPSG:4326":
    sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")

# Plot standard Cartopy Land and Coastlines underneath
ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)

# Plot high-resolution land masses on top
sis_land_boundary.plot(
    ax=ax,
    facecolor=MappingConfig.COLOR_LAND,
    edgecolor=MappingConfig.COLOR_LAND_EDGE,
    linewidth=MappingConfig.LINEWIDTH_LAND,
    transform=ccrs.PlateCarree(),
    zorder=MappingConfig.ZORDER_LAND
)
```

> [!NOTE]
> When mapping all of Japan or zooming into Seto Inland Sea using the nation-wide boundary, crop the viewport using explicit map bounds:
> ```python
> min_lon, max_lon = data_gdf['lon'].min() - 0.2, data_gdf['lon'].max() + 0.2
> min_lat, max_lat = data_gdf['lat'].min() - 0.2, data_gdf['lat'].max() + 0.2
> ax.set_xlim(min_lon, max_lon)
> ax.set_ylim(min_lat, max_lat)
> ```



---

## 4. Gridlines

```python
gl = ax.gridlines(draw_labels=True, linestyle=MappingConfig.GRID_LINESTYLE, 
                  color=MappingConfig.GRID_COLOR, alpha=MappingConfig.GRID_ALPHA, 
                  linewidth=MappingConfig.GRID_LINEWIDTH, zorder=MappingConfig.ZORDER_GRIDLINES)
# CRITICAL: The Gridliner object itself must have its zorder set,
# otherwise its draw() method is called too early (default zorder=2)
gl.set_zorder(MappingConfig.ZORDER_GRIDLINES)

# CRITICAL: Cartopy requires explicit zorder on the line artists themselves
gl.xlines.set_zorder(MappingConfig.ZORDER_GRIDLINES)
gl.ylines.set_zorder(MappingConfig.ZORDER_GRIDLINES)
gl.top_labels = False
gl.right_labels = False
```

---

## 5. Map Extent

Dynamically crop to the dataset being visualized using a proportional 11% buffer, ensuring that narrow bays (e.g. Tokyo Bay) do not end up with excessive ocean padding:

```python
# 1. First, fetch the dynamically calculated extent bounds from MappingConfig
extent = MappingConfig.get_dynamic_extent(MappingConfig.TARGET_REGION, plot_data=data_gdf)

# 2. Automatically calculate the perfect figsize to avoid Cartopy aspect ratio squishing
fig_width, fig_height = MappingConfig.get_dynamic_figsize(extent, base_width=8)
fig, ax = plt.subplots(figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})

# ... other map setups ...

# 3. Set the extent
ax.set_extent(extent, crs=ccrs.PlateCarree())
```

> [!TIP]
> `MappingConfig.get_dynamic_extent()` automatically handles the Seto Inland Sea by bypassing the 11% proportional buffer and applying the exact fixed geographical bounding box based on the `sea_area_mask_sis_simplified.shp` bounds to maintain historical standard consistency.

---

## 6. Z-Order Management

| Z-Order | Config Variable | Layer                                      |
| :------ | :---------------------------------- | :----------------------------------------- |
| base    | `ZORDER_OCEAN` | Ocean background (`set_facecolor`)         |
| 0.5     | `ZORDER_CARTOPY_LAND`| Cartopy background land |
| 0.6     | `ZORDER_CARTOPY_COASTLINE`| Cartopy background coastline |
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
import cartopy.feature as cfeature
from scripts.paths import ProjectPaths

fig, ax = plt.subplots(figsize=(10, 8), subplot_kw={'projection': ccrs.PlateCarree()})
ax.set_facecolor('lightblue')

# Load Computational Water Mask to get Extents
water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_sis_simplified.shp"
sis_water_boundary = gpd.read_file(water_boundary_path)
if sis_water_boundary.crs != "EPSG:4326":
    sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
bounds = sis_water_boundary.total_bounds

# Plot general Cartopy features
ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)

# Load and Plot High-Res Landmass Mask
land_boundary_file = MappingConfig.get_boundary_file(MappingConfig.TARGET_REGION)
land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / land_boundary_file
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

# Extent (using the water bounds or filtered data bounds)
# NOTE: For regional analysis (e.g. Tokyo Bay), the extent should follow the data_gdf bounds.
ax.set_extent([bounds[0]+0.1, bounds[2]+0.1, bounds[1]-0, bounds[3]+0.2],
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

---

## 10. Automated Verification Protocol

When creating code for a mass-produced map loop or long-running script that generates plots, follow these steps:
1. **Create a test script** (e.g., using `run_command` and python) that produces a single representative test plot.
2. **Conduct automated verification** by executing the script and inspecting the output, focusing explicitly on checking appropriate metric spacing between subplots and overall Cartopy compliance.
3. **Delete the test script and plot** once verification passes.
4. **Proceed with the main task** applying the validated layout code.

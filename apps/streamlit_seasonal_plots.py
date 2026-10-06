import sys
import yaml
from pathlib import Path

import streamlit as st
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from shapely.geometry import Point
import pyproj
from scipy.spatial import cKDTree
import scipy.ndimage as ndimage
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon

# Add project root to path for local imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

# ---------------------------------------------------------------------------
# Cached Data Loading & Geometry Setup
# ---------------------------------------------------------------------------
@st.cache_data
def load_config():
    with open(ProjectPaths.PROJECT_ROOT / "params.yaml", "r") as f:
        params = yaml.safe_load(f)
    return params.get('seasonal_plots', {})

@st.cache_resource
def load_geometries(basin_name):
    basin_files = {
        "Seto Inland Sea": "sea_area_mask_sis_simplified.shp",
        "Tokyo Bay": "sea_area_mask_Tokyo.shp",
        "Ise Mikawa Bay": "sea_area_mask_Ise.shp"
    }
    water_filename = basin_files.get(basin_name, "sea_area_mask_sis_simplified.shp")
    water_boundary_file = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / water_filename
    boundaries_gdf = gpd.read_file(water_boundary_file).to_crs("EPSG:4326")
    bounds = boundaries_gdf.total_bounds
    
    land_boundary_file = ProjectPaths.BOUNDARIES_DIR / "Whole nation administrative boundary" / "N03-20240101_prefecture(simplified0.01).shp"
    sis_land_boundary = gpd.read_file(land_boundary_file).to_crs("EPSG:4326")
    
    utm_crs = 'EPSG:32653'
    sis_water_utm = boundaries_gdf.to_crs(utm_crs)
    bounds_utm = sis_water_utm.total_bounds
    
    return bounds, sis_land_boundary, sis_water_utm, bounds_utm

@st.cache_resource
def compute_grids_and_masks(bounds_utm, _sis_water_utm, grid_res):
    # compute_grid_geometry
    grid_x_1d = np.arange(bounds_utm[0], bounds_utm[2], grid_res)
    grid_y_1d = np.arange(bounds_utm[1], bounds_utm[3], grid_res)
    grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)
    
    utm_crs = 'EPSG:32653'
    transformer = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
    flat_x = grid_x.flatten()
    flat_y = grid_y.flatten()
    
    lon_flat, lat_flat = transformer.transform(flat_x, flat_y)
    lon_wgs = lon_flat.reshape(grid_x.shape)
    lat_wgs = lat_flat.reshape(grid_y.shape)
    
    # create_mask_and_kdtree
    import shapely.prepared
    water_polygon = _sis_water_utm.geometry.union_all()
    prepared_poly = shapely.prepared.prep(water_polygon)
    grid_points = [Point(x, y) for x, y in zip(flat_x, flat_y)]
    valid_points_mask = np.array([prepared_poly.contains(pt) for pt in grid_points])
    water_mask = valid_points_mask.reshape(grid_x.shape)
    
    water_iy, water_ix = np.where(water_mask)
    water_coords = np.column_stack([grid_x[water_iy, water_ix],
                                     grid_y[water_iy, water_ix]])
    tree = cKDTree(water_coords)
    
    # get_sor_helper_matrices
    kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    water_float = water_mask.astype(np.float64)
    W = ndimage.convolve(water_float, kernel, mode='constant', cval=0.0)
    valid_W_mask = W > 0

    i_indices, j_indices = np.indices(grid_x.shape)
    red_mask = (i_indices + j_indices) % 2 == 0
    black_mask = ~red_mask
    
    return grid_x, grid_y, lon_wgs, lat_wgs, water_mask, tree, water_iy, water_ix, kernel, W, valid_W_mask, red_mask, black_mask

@st.cache_resource
def build_land_patches(_gdf, facecolor, edgecolor, linewidth):
    patches = []
    for geom in _gdf.geometry:
        if geom.geom_type == 'Polygon':
            patches.append(MplPolygon(np.array(geom.exterior.coords), closed=True))
        elif geom.geom_type == 'MultiPolygon':
            for poly in geom.geoms:
                patches.append(MplPolygon(np.array(poly.exterior.coords), closed=True))
    return patches, facecolor, edgecolor, linewidth

# ---------------------------------------------------------------------------
# Parameter Registry
# ---------------------------------------------------------------------------
BASIN_FILES = {
    "Seto Inland Sea": "merged_gdf.feather",
    "Tokyo Bay": "tokyo_bay_gdf.feather",
    "Ise Mikawa Bay": "ise_bay_gdf.feather"
}

# Reference table from the main pipeline (provides units for the core parameters)
TS_PARAMS_CSV = ProjectPaths.PROJECT_ROOT / "step5_environmental_factor_correlation_analysis" / "step5_ts_parameters.csv"

# Measured parameters: mirrors `primary_cols` in utils/data_loader.clean_and_process_data,
# plus physical columns that are stored as strings in the raw shapefiles.
# Format: column -> (display name, fallback unit)
MEASURED_PARAMS = {
    'do_':        ('DO', 'mg/L'),
    'wtemp':      ('Water Temperature', '\u00b0C'),
    'temp':       ('Air Temperature', '\u00b0C'),
    'salt':       ('Salinity', 'PSU'),
    'ph':         ('pH', ''),
    'cod':        ('COD', 'mg/L'),
    'rcod':       ('R-COD', 'mg/L'),
    'nh4n':       ('NH4-N', 'mg/L'),
    'no2n':       ('NO2-N', 'mg/L'),
    'no3n':       ('NO3-N', 'mg/L'),
    'tn':         ('TN', 'mg/L'),
    'po4p':       ('PO4-P (DIP)', 'mg/L'),
    'tp':         ('TP', 'mg/L'),
    'chlorophyl': ('Chl-a', '\u03bcg/L'),
    'feiochin':   ('Pheophytin', '\u03bcg/L'),
    'toc':        ('TOC', 'mg/L'),
    'doc':        ('DOC', 'mg/L'),
    'clearness':  ('Transparency', 'm'),
    'fusoku':     ('Wind Speed', 'm/s'),
    'depth':      ('Water Depth', 'm'),
    'saisuidept': ('Sampling Depth', 'm'),
}

# Derived parameters (computed the same way as step5/step6 pipeline scripts)
DERIVED_PARAMS = {
    'din':            ('DIN', 'mg/L'),
    'density':        ('Density (\u03c3\u03b8)', 'kg/m\u00b3'),
    'stratification': ('Stratification (\u0394\u03c3\u03b8/\u0394z, bottom\u2212surface)', 'kg/m\u00b3'),
}

# Alternate (v2) columns in the raw data -> their primary alias
V2_PARAMS = {
    'do_2': 'do_', 'ph2': 'ph', 'salt2': 'salt', 'cod2': 'cod', 'rcod2': 'rcod',
    'nh4n2': 'nh4n', 'no2n2': 'no2n', 'no3n2': 'no3n', 'tn2': 'tn', 'po4p2': 'po4p',
    'tp2': 'tp', 'chloroph_1': 'chlorophyl', 'feiochin2': 'feiochin',
    'toc2': 'toc', 'doc2': 'doc',
}

# Parameters that combine both layers (layer selector is ignored)
LAYERLESS_PARAMS = {'stratification'}


@st.cache_data
def load_unit_overrides():
    """Units from the pipeline's step5_ts_parameters.csv take priority over fallbacks."""
    if not TS_PARAMS_CSV.exists():
        return {}
    ts = pd.read_csv(TS_PARAMS_CSV)
    return ts.drop_duplicates('col').set_index('col')['unit'].dropna().to_dict()


def param_info(col):
    """Return (display name, unit, base column) for a parameter column."""
    units = load_unit_overrides()
    base = V2_PARAMS.get(col, col)
    name, unit = {**MEASURED_PARAMS, **DERIVED_PARAMS}.get(base, (col, ''))
    unit = units.get(base, unit)
    if col in V2_PARAMS:
        name = f"{name} [v2: {col}]"
    return name, unit, base


@st.cache_data(show_spinner=False)
def load_basin_df(basin_name):
    """Load a basin once, keep only needed columns, coerce to numeric and add derived params."""
    file_path = ProjectPaths.PROCESSED_DATA_DIR / BASIN_FILES[basin_name]
    if not file_path.exists():
        return None
    df = pd.read_feather(file_path)

    value_cols = [c for c in list(MEASURED_PARAMS) + list(V2_PARAMS) if c in df.columns]
    df = df[['zettaicode', 'latitude', 'longitude', 'year', 'season', 'saisuipoin'] + value_cols].copy()

    # Raw Tokyo/Ise (and some SIS) columns are strings, incl. LOD markers -> NaN
    df[value_cols] = df[value_cols].apply(pd.to_numeric, errors='coerce')
    df['saisuipoin'] = pd.to_numeric(df['saisuipoin'], errors='coerce')

    # DIN = NH4-N + NO2-N + NO3-N (all-missing rows stay NaN instead of 0)
    if {'nh4n', 'no2n', 'no3n'} <= set(df.columns):
        df['din'] = df[['nh4n', 'no2n', 'no3n']].sum(axis=1, min_count=1)

    # Potential density anomaly via TEOS-10 (same approach as step6 process02)
    if {'salt', 'wtemp'} <= set(df.columns):
        try:
            import gsw
            salt = df['salt'].fillna(df['salt2']) if 'salt2' in df.columns else df['salt']
            SA = gsw.SA_from_SP(salt.values, 0, df['longitude'].values, df['latitude'].values)
            CT = gsw.CT_from_t(SA, df['wtemp'].values, 0)
            df['density'] = gsw.sigma0(SA, CT)
        except ImportError:
            pass
    return df


def get_available_params(df):
    """All parameters with at least one valid value in this basin."""
    candidates = list(MEASURED_PARAMS) + [c for c in DERIVED_PARAMS if c != 'stratification'] + list(V2_PARAMS)
    params = [c for c in candidates if c in df.columns and df[c].notna().any()]
    if 'density' in params and 'saisuidept' in params:
        params.insert(params.index('density') + 1, 'stratification')
    return params


@st.cache_data
def load_station_data(basin_name):
    df = load_basin_df(basin_name)
    stations_df = df[['zettaicode', 'latitude', 'longitude']].drop_duplicates(subset=['zettaicode'])
    stations_df['station_id'] = stations_df['zettaicode']
    stations_df.set_index('station_id', inplace=True)
    stations_gdf = gpd.GeoDataFrame(stations_df, 
                                    geometry=gpd.points_from_xy(stations_df.longitude, stations_df.latitude), 
                                    crs="EPSG:4326")
    utm_crs = 'EPSG:32653'
    stations_utm = stations_gdf.to_crs(utm_crs)
    return stations_gdf, stations_utm

@st.cache_data(show_spinner=False)
def load_yearly_data(basin_name, season, layer, parameter):
    """Station x year table of seasonal means for the chosen parameter/layer."""
    df = load_basin_df(basin_name)
    if df is None:
        return None
    df = df[df['season'] == season]

    if parameter == 'stratification':
        # (density_bottom - density_surface) / (depth_bottom - depth_surface), per station-year
        g = (df.groupby(['zettaicode', 'year', 'saisuipoin'])[['density', 'saisuidept']]
               .mean().unstack('saisuipoin'))
        if 1 not in g['density'].columns or 2 not in g['density'].columns:
            return None
        dz = (g[('saisuidept', 2)] - g[('saisuidept', 1)]).replace(0, np.nan)
        series = (g[('density', 2)] - g[('density', 1)]) / dz
    else:
        if parameter not in df.columns:
            return None
        layer_code = 1 if layer == "surface" else 2
        df = df[df['saisuipoin'] == layer_code]
        series = df.groupby(['zettaicode', 'year'])[parameter].mean()

    pivot_df = series.unstack('year').dropna(axis=1, how='all').dropna(axis=0, how='all')
    if pivot_df.empty:
        return None
    pivot_df.columns = pivot_df.columns.astype(str)
    return pivot_df


def get_plot_settings(parameter, pivot_df):
    """Use MappingConfig styling when defined; otherwise derive a robust range from the data."""
    name, unit, base = param_info(parameter)
    if base in MappingConfig.VARIABLE_SETTINGS:
        cfg = dict(MappingConfig.get_var_settings(base))
        cfg['source'] = 'config'
    else:
        vals = pivot_df.to_numpy(dtype=float).ravel()
        vals = vals[np.isfinite(vals)]
        lo, hi = (np.percentile(vals, [2, 98]) if vals.size else (0.0, 1.0))
        if hi <= lo:
            hi = lo + 1.0
        cfg = {'cmap': 'viridis', 'vmin': float(lo), 'vmax': float(hi),
               'extend': 'both', 'source': 'auto',
               'label': f"{name} ({unit})" if unit else name}
    cfg['base'] = base
    return cfg

# ---------------------------------------------------------------------------
# Solver and Plotting Functions
# ---------------------------------------------------------------------------

def run_diffusion_interpolation(plot_df, stations_utm,
                                water_mask, water_tree, water_iy, water_ix,
                                kernel, W, valid_W_mask, red_mask, black_mask, parameter,
                                max_iters=500, tol=1e-3, omega=1.8):
    Z = np.full(water_mask.shape, np.nan)
    mean_val = plot_df[parameter].mean()
    Z[water_mask] = mean_val
    fixed_mask = np.zeros_like(water_mask, dtype=bool)

    common_ids = plot_df.index.intersection(stations_utm.index)
    if len(common_ids) == 0:
        return Z

    pts_x = stations_utm.loc[common_ids].geometry.x.values
    pts_y = stations_utm.loc[common_ids].geometry.y.values
    do_vals = plot_df.loc[common_ids, parameter].values

    station_coords = np.column_stack([pts_x, pts_y])
    _, nearest_idx = water_tree.query(station_coords)

    for k in range(len(common_ids)):
        iy = water_iy[nearest_idx[k]]
        ix = water_ix[nearest_idx[k]]
        Z[iy, ix] = do_vals[k]
        fixed_mask[iy, ix] = True

    Z_water = np.zeros_like(Z)

    for it in range(max_iters):
        Z_old_water = Z[water_mask].copy()

        with np.errstate(divide='ignore', invalid='ignore'):
            Z_water[:] = 0.0
            Z_water[water_mask] = Z[water_mask]
            Z_sum = ndimage.convolve(Z_water, kernel, mode='constant', cval=0.0)
            Z_avg = np.where(valid_W_mask, Z_sum / W, Z)
            update_red = red_mask & water_mask & (~fixed_mask)
            Z[update_red] = (1 - omega) * Z[update_red] + omega * Z_avg[update_red]

            Z_water[:] = 0.0
            Z_water[water_mask] = Z[water_mask]
            Z_sum = ndimage.convolve(Z_water, kernel, mode='constant', cval=0.0)
            Z_avg = np.where(valid_W_mask, Z_sum / W, Z)
            update_black = black_mask & water_mask & (~fixed_mask)
            Z[update_black] = (1 - omega) * Z[update_black] + omega * Z_avg[update_black]

        max_diff = np.max(np.abs(Z[water_mask] - Z_old_water))
        if max_diff < tol:
            break

    return Z

def add_land_to_ax(ax, patches_data):
    patches, fc, ec, lw = patches_data
    pc = PatchCollection(
        [MplPolygon(p.get_xy(), closed=True) for p in patches],
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_LAND
    )
    ax.add_collection(pc)

def draw_map_on_ax(ax, plot_df, Z, lon_wgs, lat_wgs, parameter, var_cfg, bounds, land_patches, draw_labels=True):
    vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
    cmap = var_cfg['cmap']
    
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    
    ax.set_extent([bounds[0]-0.2, bounds[2]+0.2, bounds[1]-0.2, bounds[3]+0.2],
                  crs=ccrs.PlateCarree())

    add_land_to_ax(ax, land_patches)
                   
    gl = ax.gridlines(draw_labels=draw_labels, 
                      linestyle=MappingConfig.GRID_LINESTYLE, 
                      color=MappingConfig.GRID_COLOR, 
                      alpha=MappingConfig.GRID_ALPHA, 
                      linewidth=MappingConfig.GRID_LINEWIDTH, 
                      zorder=MappingConfig.ZORDER_GRIDLINES)
    gl.top_labels = False
    gl.right_labels = False
                   
    c_m = ax.pcolormesh(lon_wgs, lat_wgs, Z,
                        transform=ccrs.PlateCarree(),
                        cmap=cmap, shading='nearest',
                        zorder=MappingConfig.ZORDER_PREDICTED,
                        vmin=vmin, vmax=vmax)
                        
    ax.scatter(plot_df['longitude'], plot_df['latitude'],
               c=plot_df[parameter], cmap=cmap,
               edgecolors='black', linewidth=0.2,
               transform=ccrs.PlateCarree(),
               zorder=MappingConfig.ZORDER_OBSERVATIONS,
               marker='^', s=25, vmin=vmin, vmax=vmax)
               
    return c_m

# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="SIS Seasonal Spatial Distribution", layout="wide")
st.title("Interactive Seasonal Spatial Distribution")
st.markdown("Easily configure and visualize interpolation meshes instantly.")

with st.spinner("Loading configuration..."):
    config = load_config()

# Sidebar Controls
st.sidebar.header("Plot Settings")
available_basins = ["Seto Inland Sea", "Tokyo Bay", "Ise Mikawa Bay"]
selected_basin = st.sidebar.selectbox("Basin", available_basins)

with st.spinner(f"Loading {selected_basin} data, geometry & stations..."):
    basin_df = load_basin_df(selected_basin)
    if basin_df is None:
        st.error(f"Data file for {selected_basin} not found.")
        st.stop()
    bounds, sis_land_boundary, sis_water_utm, bounds_utm = load_geometries(selected_basin)
    land_patches = build_land_patches(sis_land_boundary, MappingConfig.COLOR_LAND, MappingConfig.COLOR_LAND_EDGE, MappingConfig.LINEWIDTH_LAND)
    stations_gdf, stations_utm = load_station_data(selected_basin)

available_params = get_available_params(basin_df)
selected_param = st.sidebar.selectbox(
    "Parameter", available_params,
    index=available_params.index('do_') if 'do_' in available_params else 0,
    format_func=lambda c: f"{param_info(c)[0]}  ({c})")

available_seasons = config.get('seasons', ['Spring', 'Summer', 'Autumn', 'Winter'])
selected_season = st.sidebar.selectbox("Season", available_seasons)

available_layers = config.get('layers', ['surface', 'bottom'])
selected_layer = st.sidebar.selectbox("Layer", available_layers,
                                      disabled=selected_param in LAYERLESS_PARAMS)
if selected_param in LAYERLESS_PARAMS:
    st.sidebar.caption("Stratification uses both layers (bottom \u2212 surface).")

with st.spinner("Pivoting data table..."):
    df_param = load_yearly_data(selected_basin, selected_season, selected_layer, selected_param)
if df_param is None:
    st.error(f"No data found for {selected_basin} {selected_season} {selected_layer} {selected_param}.")
    st.stop()

years = [c for c in df_param.columns if c.isdigit()]
selected_year = st.sidebar.selectbox("Year", sorted(years, reverse=True))

# Colour scale (defaults: MappingConfig if defined, else 2nd-98th percentile over all years)
var_cfg = get_plot_settings(selected_param, df_param)
st.sidebar.header("Colour Scale")
custom_range = st.sidebar.checkbox("Custom colour range", value=False)
if custom_range:
    range_key = f"{selected_basin}_{selected_param}_{selected_season}_{selected_layer}"
    c1, c2 = st.sidebar.columns(2)
    var_cfg['vmin'] = c1.number_input("Min", value=float(var_cfg['vmin']), format="%.3f", key=f"vmin_{range_key}")
    var_cfg['vmax'] = c2.number_input("Max", value=float(var_cfg['vmax']), format="%.3f", key=f"vmax_{range_key}")
    if var_cfg['vmax'] <= var_cfg['vmin']:
        st.sidebar.error("Max must be greater than Min.")
        st.stop()
else:
    range_src = 'MappingConfig' if var_cfg['source'] == 'config' else 'auto, 2\u201398th pct'
    st.sidebar.caption(f"Range: {var_cfg['vmin']:.3g} \u2013 {var_cfg['vmax']:.3g} ({range_src})")

st.sidebar.header("Solver Options")
grid_res = st.sidebar.slider("Grid Resolution (m) [Higher = Faster]", 2000, 10000, 4000, step=1000)
max_iters = st.sidebar.slider("Max Solver Iterations", 100, 1000, 300, step=100)
tol = st.sidebar.number_input("Solver Tolerance", value=1e-3, format="%.4f")

if st.sidebar.button("Render Plot", type="primary"):
    with st.spinner("Preparing grids..."):
        grid_x, grid_y, lon_wgs, lat_wgs, water_mask, tree, water_iy, water_ix, kernel, W, valid_W_mask, red_mask, black_mask = compute_grids_and_masks(bounds_utm, sis_water_utm, grid_res)
        
    with st.spinner("Running diffusion solver..."):
        values = df_param[[selected_year]].dropna().rename(columns={selected_year: selected_param})
        values.index.name = 'station_id'
        plot_df = values.join(stations_gdf, how='inner')
        
        if plot_df.empty:
            st.error("No valid data points found for this selection.")
            st.stop()
            
        Z = run_diffusion_interpolation(plot_df, stations_utm,
                                        water_mask, tree, water_iy, water_ix,
                                        kernel, W, valid_W_mask, red_mask, black_mask, selected_param,
                                        max_iters=max_iters, tol=tol)
                                        
    with st.spinner("Rendering plot..."):
        fig, ax = plt.subplots(figsize=(14, 10), subplot_kw={'projection': ccrs.PlateCarree()})
        c_m = draw_map_on_ax(ax, plot_df, Z, lon_wgs, lat_wgs, selected_param, var_cfg, bounds, land_patches, draw_labels=True)
        
        layer_label = "bottom \u2212 surface" if selected_param in LAYERLESS_PARAMS else selected_layer
        ax.set_title(f"{selected_year} {selected_season} ({layer_label})", fontsize=14)
        cbar = plt.colorbar(c_m, ax=ax, shrink=0.7, extend=var_cfg.get('extend', 'both'))
        if var_cfg['source'] == 'config' and not custom_range:
            MappingConfig.format_colorbar_ticks(cbar, var_cfg['base'])
        cbar.set_label(var_cfg['label'], fontsize=14)
        
        st.pyplot(fig)
        plt.close(fig)
        st.caption(f"{param_info(selected_param)[0]} \u2014 {len(plot_df)} stations with data in {selected_year}.")
else:
    st.info("Select parameters and click 'Render Plot' to view the map.")

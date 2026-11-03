# -*- coding: utf-8 -*-
"""
Sandbox Script 82: Study-area overview map of Japan.
Draws the Japan coastline with the study water masses (Seto Inland Sea, Ise-Mikawa Bay, Tokyo Bay)
highlighted, a zebra lat/lon border on all four sides, a legend and a scale bar.
The extent mimics the site-location maps of the Ministry of the Environment.
Parameters are read from 82_study_area_overview_map_parameters.csv.
"""

import sys
import shutil
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from matplotlib.patches import Patch, Rectangle

plt.style.use(str(Path(__file__).resolve().parent.parent / 'project_style.mplstyle'))

from utils.paths import ProjectPaths

# Directories
STEP_DIR = "step0_sandbox"
SCRIPT_NAME = "82_study_area_overview_map"
OUTPUT_DIR = ProjectPaths.PROJECT_ROOT / "figures" / STEP_DIR / SCRIPT_NAME
PARAM_FILE = Path(__file__).resolve().parent / "82_study_area_overview_map_parameters.csv"

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Input boundaries
JAPAN_FILE = ProjectPaths.BOUNDARIES_DIR / "Whole nation administrative boundary" / "N03-20240101_prefecture(simplified0.005).shp"
MASK_DIR = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon"
WATER_MASSES = {
    "Seto Inland Sea": (MASK_DIR / "sea_area_mask_sis_simplified.shp", "tab:red"),
    "Ise-Mikawa Bay": (MASK_DIR / "sea_area_mask_Ise.shp", "tab:orange"),
    "Tokyo Bay": (MASK_DIR / "sea_area_mask_Tokyo.shp", "tab:blue"),
}

# Font sizes (hardcoded per spec, overriding the project style)
LABEL_FONTSIZE = 18         # zebra border labels and scale bar labels
LEGEND_FONTSIZE = 18        # legend entries
LEGEND_TITLE_FONTSIZE = 20  # legend title

PROJ = ccrs.Mercator()
PC = ccrs.PlateCarree()


def check_inputs():
    """Return True if the parameter file and all boundary files exist; log a warning otherwise."""
    required = [PARAM_FILE, JAPAN_FILE] + [path for path, _ in WATER_MASSES.values()]
    missing = [p for p in required if not p.exists()]
    if missing:
        logging.warning(f"Missing input files, skipping script 82: {missing}")
        return False
    return True


def load_params():
    """Load parameters from the CSV into a dict of floats."""
    df = pd.read_csv(PARAM_FILE)
    return {row['parameter_name']: float(row['value']) for _, row in df.iterrows()}


def load_land():
    """Japan coastline as a single polygon (prefecture borders dissolved)."""
    japan = gpd.read_file(JAPAN_FILE).to_crs("EPSG:4326")
    # The small buffer closes slivers between adjacent prefecture polygons before dissolving
    return gpd.GeoSeries([japan.geometry.buffer(0.003).union_all().buffer(-0.003)], crs="EPSG:4326")


def load_water_mass(path):
    """Water-mass polygon reprojected to EPSG:4326 (the SIS mask has no CRS embedded in some copies)."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:32653")
    return gdf.to_crs("EPSG:4326")


def zebra_edges(lo, hi, step):
    """Segment boundaries from lo to hi, split at multiples of step."""
    ticks = np.arange(np.ceil(lo / step) * step, hi, step)
    return np.concatenate([[lo], ticks[ticks > lo], [hi]])


def draw_zebra_border(ax, extent, map_width, map_height, step, band_inches):
    """Alternating black/white lat/lon segments on all four sides; labels on bottom and left."""
    xmin, ymin = PROJ.transform_point(extent[0], extent[2], PC)
    xmax, ymax = PROJ.transform_point(extent[1], extent[3], PC)
    lon_edges = zebra_edges(extent[0], extent[1], step)
    lat_edges = zebra_edges(extent[2], extent[3], step)
    # Segment positions in axes fractions (Mercator is non-linear in latitude)
    lon_ax = [(PROJ.transform_point(l, extent[2], PC)[0] - xmin) / (xmax - xmin) for l in lon_edges]
    lat_ax = [(PROJ.transform_point(extent[0], l, PC)[1] - ymin) / (ymax - ymin) for l in lat_edges]
    bw_x, bw_y = band_inches / map_width, band_inches / map_height

    def patch(x, y, w, h, color):
        ax.add_patch(Rectangle((x, y), w, h, transform=ax.transAxes, clip_on=False, zorder=20,
                               facecolor=color, edgecolor="black", linewidth=0.8))

    for i in range(len(lon_ax) - 1):
        for y in (-bw_y, 1):  # bottom, top
            patch(lon_ax[i], y, lon_ax[i + 1] - lon_ax[i], bw_y, "black" if i % 2 == 0 else "white")
    for i in range(len(lat_ax) - 1):
        for x in (-bw_x, 1):  # left, right
            patch(x, lat_ax[i], bw_x, lat_ax[i + 1] - lat_ax[i], "black" if i % 2 == 0 else "white")
    for x in (-bw_x, 1):  # corner squares close the frame
        for y in (-bw_y, 1):
            patch(x, y, bw_x, bw_y, "white")

    for l, xa in zip(lon_edges[1:-1], lon_ax[1:-1]):
        ax.text(xa, -bw_y - 0.006, f"{abs(l):g}°{'E' if l >= 0 else 'W'}", transform=ax.transAxes,
                ha="center", va="top", fontsize=LABEL_FONTSIZE)
    for l, ya in zip(lat_edges[1:-1], lat_ax[1:-1]):
        ax.text(-bw_x - 0.004, ya, f"{abs(l):g}°{'N' if l >= 0 else 'S'}", transform=ax.transAxes,
                ha="right", va="center", fontsize=LABEL_FONTSIZE)


def draw_scale_bar(ax, lon0, lat0, length_km):
    """Scale bar with 0 / half / full ticks. Mercator units are stretched by 1/cos(lat), so the
    bar length is corrected at the bar's latitude."""
    x0, y0 = PROJ.transform_point(lon0, lat0, PC)
    length = length_km * 1e3 / np.cos(np.radians(lat0))
    labels = [(0, "0"), (0.5, f"{length_km / 2:g}"), (1, f"{length_km:g}km")]
    for frac, lab in labels:
        ax.plot([x0 + frac * length] * 2, [y0 - 8e3, y0 + 8e3], color="black", lw=1.2, transform=PROJ, zorder=10)
        ax.text(x0 + frac * length, y0 + 18e3, lab, ha="center", va="bottom", fontsize=LABEL_FONTSIZE, transform=PROJ, zorder=10)
    ax.plot([x0, x0 + length], [y0, y0], color="black", lw=3, transform=PROJ, zorder=10)


def plot_overview_map(p):
    """Build and save the overview map; returns the output path."""
    extent = [p['extent_lon_min'], p['extent_lon_max'], p['extent_lat_min'], p['extent_lat_max']]
    map_width, margin = p['map_width_inches'], p['margin_inches']

    # Figure sized so the Mercator map is undistorted (no cartopy aspect shrinking)
    xmin, ymin = PROJ.transform_point(extent[0], extent[2], PC)
    xmax, ymax = PROJ.transform_point(extent[1], extent[3], PC)
    map_height = map_width * (ymax - ymin) / (xmax - xmin)
    fig_w, fig_h = map_width + 2 * margin, map_height + 2 * margin
    fig = plt.figure(figsize=(fig_w, fig_h))
    ax = fig.add_axes([margin / fig_w, margin / fig_h, map_width / fig_w, map_height / fig_h], projection=PROJ)
    ax.set_extent(extent, crs=PC)
    ax.set_facecolor("white")
    ax.spines["geo"].set_linewidth(1.0)

    ax.add_geometries(load_land(), crs=PC, facecolor="white", edgecolor="black", linewidth=0.6, zorder=1)

    handles = []
    for name, (path, color) in WATER_MASSES.items():
        ax.add_geometries(load_water_mass(path).geometry, crs=PC, facecolor=color, alpha=0.6,
                          edgecolor=color, linewidth=1.0, zorder=2)
        handles.append(Patch(facecolor=color, edgecolor=color, alpha=0.6, label=name))
    ax.legend(handles=handles, loc="upper left", fontsize=LEGEND_FONTSIZE, frameon=True, edgecolor="black",
              title="Study area water masses", title_fontsize=LEGEND_TITLE_FONTSIZE).set_zorder(10)

    draw_scale_bar(ax, p['scale_bar_lon'], p['scale_bar_lat'], p['scale_bar_km'])
    draw_zebra_border(ax, extent, map_width, map_height, p['zebra_step_degrees'], p['zebra_width_inches'])

    out = OUTPUT_DIR / (f"study_area_overview_map_lon{extent[0]:g}-{extent[1]:g}_lat{extent[2]:g}-{extent[3]:g}"
                        f"_zebra{p['zebra_step_degrees']:g}deg.png")
    fig.savefig(out, dpi=int(p['dpi']))
    plt.close(fig)
    return out


def main():
    if not check_inputs():
        return
    params = load_params()
    # Script owns its output folder: clear before writing
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = plot_overview_map(params)
    logging.info(f"Saved {out}")


if __name__ == "__main__":
    main()

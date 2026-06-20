"""
Conceptual Visualization: Spatial Interpolation Method
=======================================================
Illustrates the Gaussian-weighted spatial interpolation used in:
    09_Spatial_Interpolation_v2.ipynb

Two panels:
  Left  — Spatial layout: target station (missing value) with neighbours
          colour-coded by their Gaussian weight.  Search radius = 2× decorr. scale shown.
  Right — Weight function curves (Gaussian & Exponential) over distance, with
          decorrelation scale and search radius annotated.
"""

import matplotlib
matplotlib.use('Agg')   # headless – no display needed
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrow, Circle
from matplotlib.gridspec import GridSpec
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import matplotlib.patheffects as pe

# ── Reproducible synthetic layout ─────────────────────────────────────────────
np.random.seed(42)

DECORR_SCALE = 25          # km  (decorrelation scale of the target station)
SEARCH_RADIUS = 2 * DECORR_SCALE   # km  (search radius = 2× decorr. scale)
MIN_WEIGHT = 0.01

# Target station (missing DO value this year)
target_xy = np.array([0.0, 0.0])

# Generate candidate neighbouring stations
angles = np.linspace(0, 2 * np.pi, 14, endpoint=False) + 0.3
radii  = [10, 18, 22, 28, 35, 42, 50, 60, 68, 75, 85, 92, 48, 15]
neigh_xy = np.column_stack([
    np.array(radii) * np.cos(angles),
    np.array(radii) * np.sin(angles),
])
distances = np.linalg.norm(neigh_xy - target_xy, axis=1)

# Gaussian weight function  w(d) = exp(-d² / (2·σ²))
def gaussian_weight(d, scale):
    return np.exp(-(d**2) / (2 * scale**2))

weights = gaussian_weight(distances, DECORR_SCALE)
inside  = distances <= SEARCH_RADIUS
valid   = inside & (weights > MIN_WEIGHT)


# ── Colour helpers ─────────────────────────────────────────────────────────────
PALETTE = {
    'bg':          '#0f1117',
    'panel':       '#181c27',
    'accent1':     '#4f8ef7',   # blue — target station
    'accent2':     '#f75d4f',   # red  — outside radius
    'accent3':     '#2ecc71',   # green — search radius ring
    'accent4':     '#f7c948',   # yellow — decorr scale ring
    'grid':        '#2a2f3f',
    'text':        '#dce3f0',
    'subtext':     '#8591a8',
    'gaussian':    '#4f8ef7',
    'exponential': '#e88c2a',
    'threshold':   '#2ecc71',
    'radius':      '#f7c948',
}

# Colourmap for neighbour weights (grey→cyan)
cmap = plt.colormaps['cool']
norm = Normalize(vmin=0, vmax=1)

# ── Figure setup ────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 7.5), facecolor=PALETTE['bg'])
gs  = GridSpec(1, 2, figure=fig, wspace=0.10,
               left=0.04, right=0.97, top=0.88, bottom=0.10)

ax_map  = fig.add_subplot(gs[0])
ax_wfn  = fig.add_subplot(gs[1])

for ax in (ax_map, ax_wfn):
    ax.set_facecolor(PALETTE['panel'])
    ax.tick_params(colors=PALETTE['subtext'])
    for spine in ax.spines.values():
        spine.set_edgecolor(PALETTE['grid'])
    ax.grid(color=PALETTE['grid'], linestyle='--', linewidth=0.6, alpha=0.7)
    ax.title.set_color(PALETTE['text'])
    ax.xaxis.label.set_color(PALETTE['text'])
    ax.yaxis.label.set_color(PALETTE['text'])

# ═══════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — Spatial layout
# ═══════════════════════════════════════════════════════════════════════════════
ax = ax_map

lim = 105
ax.set_xlim(-lim, lim)
ax.set_ylim(-lim, lim)
ax.set_aspect('equal')
ax.set_xlabel('East–West Distance  (km)', fontsize=11)
ax.set_ylabel('North–South Distance  (km)', fontsize=11)
ax.set_title('Spatial Layout: Gaussian-Weighted Interpolation', fontsize=13, fontweight='bold', pad=10)

# ── Dashed rings: decorrelation scale & search radius ─────────────────────────
ring_decorr = plt.Circle(target_xy, DECORR_SCALE, fill=False,
                          edgecolor=PALETTE['accent4'], linestyle='--',
                          linewidth=1.8, zorder=3, label=f'Decorr. scale  (σ = {DECORR_SCALE} km)')
ring_search = plt.Circle(target_xy, SEARCH_RADIUS, fill=False,
                          edgecolor=PALETTE['accent3'], linestyle='-.',
                          linewidth=2.2, zorder=3, label=f'Search radius  (2σ = {SEARCH_RADIUS} km)')
ax.add_patch(ring_decorr)
ax.add_patch(ring_search)

# ── Thin "spokes" from target to valid neighbours ─────────────────────────────
for i in range(len(distances)):
    if valid[i]:
        w = weights[i]
        ax.plot([target_xy[0], neigh_xy[i, 0]],
                [target_xy[1], neigh_xy[i, 1]],
                color=cmap(norm(w)), linewidth=1.2, alpha=0.55, zorder=2)

# ── Neighbour stations ────────────────────────────────────────────────────────
for i in range(len(distances)):
    w = weights[i]
    if valid[i]:
        colour = cmap(norm(w))
        marker_kw = dict(color=colour, s=120, zorder=5,
                         edgecolors='white', linewidths=0.7)
        ax.scatter(*neigh_xy[i], **marker_kw)
        # Weight label
        ax.annotate(f'{w:.2f}',
                    xy=neigh_xy[i], xytext=(4, 4), textcoords='offset points',
                    fontsize=7.5, color=PALETTE['text'], alpha=0.85)
    else:
        # Outside radius or below min weight — dim marker
        ax.scatter(*neigh_xy[i], color=PALETTE['accent2'], s=70,
                   alpha=0.35, zorder=4, edgecolors='none')
        ax.annotate('✗', xy=neigh_xy[i], xytext=(3, 3),
                    textcoords='offset points', fontsize=8,
                    color=PALETTE['accent2'], alpha=0.5)

# ── Target station (missing value) ────────────────────────────────────────────
ax.scatter(*target_xy, color=PALETTE['accent1'], s=260, zorder=6,
           edgecolors='white', linewidths=1.5, marker='*')
ax.annotate('Target\n(missing)', xy=target_xy, xytext=(6, 8),
            textcoords='offset points', fontsize=9,
            color=PALETTE['accent1'], fontweight='bold',
            path_effects=[pe.withStroke(linewidth=2, foreground=PALETTE['panel'])])

# ── Annotate search radius arrow ───────────────────────────────────────────────
ax.annotate('', xy=(SEARCH_RADIUS, 0), xytext=(0, 0),
            arrowprops=dict(arrowstyle='->', color=PALETTE['accent3'],
                            lw=1.8, shrinkA=10, shrinkB=4))
ax.text(SEARCH_RADIUS / 2, 3.5, f'Search radius\n= 2σ = {SEARCH_RADIUS} km',
        ha='center', va='bottom', fontsize=8.5,
        color=PALETTE['accent3'],
        path_effects=[pe.withStroke(linewidth=2, foreground=PALETTE['panel'])])

# ── Decorrelation scale arrow ─────────────────────────────────────────────────
ax.annotate('', xy=(0, -DECORR_SCALE), xytext=(0, 0),
            arrowprops=dict(arrowstyle='->', color=PALETTE['accent4'],
                            lw=1.5, linestyle='dashed',
                            shrinkA=10, shrinkB=4))
ax.text(4, -DECORR_SCALE / 2, f'σ = {DECORR_SCALE} km',
        ha='left', va='center', fontsize=8.5,
        color=PALETTE['accent4'],
        path_effects=[pe.withStroke(linewidth=2, foreground=PALETTE['panel'])])

# ── Colourbar for weights ──────────────────────────────────────────────────────
sm = ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax, shrink=0.55, pad=0.02, aspect=18)
cbar.set_label('Gaussian weight  w(d)', color=PALETTE['text'], fontsize=9)
cbar.ax.yaxis.set_tick_params(color=PALETTE['subtext'])
plt.setp(cbar.ax.yaxis.get_ticklabels(), color=PALETTE['subtext'], fontsize=8)
cbar.outline.set_edgecolor(PALETTE['grid'])

# ── Legend ─────────────────────────────────────────────────────────────────────
legend_handles = [
    mpatches.Patch(color=PALETTE['accent4'], label=f'Decorr. scale  σ = {DECORR_SCALE} km'),
    mpatches.Patch(color=PALETTE['accent3'], label=f'Search radius  2σ = {SEARCH_RADIUS} km'),
    plt.scatter([], [], color=cmap(0.8), s=80, label='Neighbour (used, w > 0.01)', edgecolors='white'),
    plt.scatter([], [], color=PALETTE['accent2'], s=60, alpha=0.45, label='Neighbour (excluded)'),
    plt.scatter([], [], color=PALETTE['accent1'], s=150, marker='*', label='Target station (missing)'),
]
leg = ax.legend(handles=legend_handles, loc='lower right', fontsize=8,
                facecolor=PALETTE['panel'], edgecolor=PALETTE['grid'],
                labelcolor=PALETTE['text'])

# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL — Weight functions
# ═══════════════════════════════════════════════════════════════════════════════
ax = ax_wfn

d = np.linspace(0, 80, 400)

w_gauss = gaussian_weight(d, DECORR_SCALE)
w_expon = np.exp(-d / DECORR_SCALE)   # exponential (alternative)

ax.plot(d, w_gauss, color=PALETTE['gaussian'],    linewidth=2.8, label='Gaussian  (used)')
ax.plot(d, w_expon, color=PALETTE['exponential'], linewidth=1.8,
        linestyle='--', label='Exponential  (alternative)', alpha=0.75)

# ── Min-weight threshold ───────────────────────────────────────────────────────
ax.axhline(MIN_WEIGHT, color=PALETTE['threshold'], linestyle=':', linewidth=1.8,
           label=f'Min-weight threshold  ({MIN_WEIGHT})')

# ── Decorrelation scale vertical line ─────────────────────────────────────────
ax.axvline(DECORR_SCALE, color=PALETTE['accent4'], linestyle='--',
           linewidth=1.8, label=f'Decorr. scale  σ = {DECORR_SCALE} km')

# ── Search radius vertical line ───────────────────────────────────────────────
ax.axvline(SEARCH_RADIUS, color=PALETTE['accent3'], linestyle='-.',
           linewidth=1.8, label=f'Search radius  2σ = {SEARCH_RADIUS} km')

# ── Highlighted fill: "accepted" zone ─────────────────────────────────────────
mask_acc = d <= SEARCH_RADIUS
ax.fill_between(d[mask_acc], 0, w_gauss[mask_acc],
                color=PALETTE['gaussian'], alpha=0.08, label='Accepted weight region')

# ── Weight at σ ───────────────────────────────────────────────────────────────
w_at_sigma = gaussian_weight(DECORR_SCALE, DECORR_SCALE)
ax.plot(DECORR_SCALE, w_at_sigma, 'o', color=PALETTE['accent4'], markersize=8, zorder=6)
ax.annotate(f'w(σ) = {w_at_sigma:.3f}',
            xy=(DECORR_SCALE, w_at_sigma),
            xytext=(DECORR_SCALE + 4, w_at_sigma + 0.05),
            fontsize=8.5, color=PALETTE['accent4'],
            arrowprops=dict(arrowstyle='->', color=PALETTE['accent4'], lw=1.2),
            path_effects=[pe.withStroke(linewidth=2, foreground=PALETTE['panel'])])

# ── Weight at 2σ ──────────────────────────────────────────────────────────────
w_at_2sigma = gaussian_weight(SEARCH_RADIUS, DECORR_SCALE)
ax.plot(SEARCH_RADIUS, w_at_2sigma, 'o', color=PALETTE['accent3'], markersize=8, zorder=6)
ax.annotate(f'w(2σ) = {w_at_2sigma:.3f}',
            xy=(SEARCH_RADIUS, w_at_2sigma),
            xytext=(SEARCH_RADIUS + 3, w_at_2sigma + 0.06),
            fontsize=8.5, color=PALETTE['accent3'],
            arrowprops=dict(arrowstyle='->', color=PALETTE['accent3'], lw=1.2),
            path_effects=[pe.withStroke(linewidth=2, foreground=PALETTE['panel'])])

# ── Formula annotation ────────────────────────────────────────────────────────
formula_txt = (
    r"$w(d)\ =\ \exp\!\left(-\dfrac{d^2}{2\,\sigma^2}\right)$"
    "\n\n"
    r"$\hat{DO}\ =\ \dfrac{\sum_i w_i\,DO_i}{\sum_i w_i}$"
)
ax.text(0.98, 0.97, formula_txt,
        transform=ax.transAxes, ha='right', va='top',
        fontsize=11, color=PALETTE['text'],
        bbox=dict(boxstyle='round,pad=0.5', facecolor=PALETTE['bg'],
                  edgecolor=PALETTE['grid'], alpha=0.85))

ax.set_xlim(0, 80)
ax.set_ylim(-0.05, 1.12)
ax.set_xlabel('Distance to Neighbour  d  (km)', fontsize=11)
ax.set_ylabel('Interpolation Weight  w(d)', fontsize=11)
ax.set_title('Weight Decay Functions & Key Thresholds', fontsize=13, fontweight='bold', pad=10)

leg2 = ax.legend(loc='upper right', fontsize=8.5,
                 facecolor=PALETTE['panel'], edgecolor=PALETTE['grid'],
                 labelcolor=PALETTE['text'],
                 bbox_to_anchor=(0.99, 0.78))

# ══ Super-title ════════════════════════════════════════════════════════════════
fig.suptitle(
    'Spatial Interpolation of Missing DO Values  ·  Gaussian Weighted Average\n'
    r'$\hat{DO}_{target}\ =\ \sum_{i\,\in\,\text{radius}} w_i\,DO_i \ /\ \sum w_i$'
    f'     |     search radius = 2σ,  σ = decorrelation scale',
    fontsize=12, color=PALETTE['text'], y=0.97, fontweight='bold'
)

# ── Save ───────────────────────────────────────────────────────────────────────
out_path = 'spatial_interpolation_diagram.png'
plt.savefig(out_path, dpi=180, bbox_inches='tight', facecolor=PALETTE['bg'])
print(f'Saved → {out_path}')
plt.show()

# -*- coding: utf-8 -*-
"""
process31_correlation_distribution.py

Summarise the station-wise Pearson correlations between the DO PCA scores
(PC1 / PC2 of one season/layer DO subset) and every environmental or nutrient
parameter permutation (parameter x parameter season x depth layer) produced by
process01.

Outputs (per target region / DO subset / data type):
    1. correlation_distribution_*.png      - boxplots of r per parameter, coloured by parameter season
    2. correlation_significance_counts_*.png - diverging counts of significant (p < 0.05) stations
"""
import argparse
import sys
from pathlib import Path
import os
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import seaborn as sns

# --- BOILERPLATE INJECTED BY AGENT ---
CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')
# -------------------------------------

project_root = CURRENT_SCRIPT.parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths

# Configure plots
plt.style.use(str(project_root / 'project_style.mplstyle'))

# Override font sizes: increase by 8
plt.rcParams['font.size'] += 8
plt.rcParams['axes.titlesize'] = 26
plt.rcParams['axes.labelsize'] = 26
plt.rcParams['xtick.labelsize'] = 24
plt.rcParams['ytick.labelsize'] = 24
plt.rcParams['legend.fontsize'] = 20
plt.rcParams['figure.titlesize'] = 28

plt.rcParams['figure.dpi'] = 150

SIG_LEVEL = 0.05
DEFAULT_SEASONS = ['Spring', 'Summer', 'Autumn', 'Winter']
SEASON_COLORS = {
    'Spring': '#66a61e',
    'Summer': '#e7298a',
    'Autumn': '#d95f02',
    'Winter': '#1f78b4',
}
LAYER_NAMES = {'1': 'Surface', '2': 'Bottom'}
NUTRIENT_LABELS = {'NH4N': 'NH4-N', 'NO2N': 'NO2-N', 'NO3N': 'NO3-N', 'PO4P': 'PO4-P'}


def load_correlation_seasons():
    """Return the parameter seasons (order used for colouring) from step5_parameter.csv."""
    param_file = CURRENT_SCRIPT.parent / 'step5_parameter.csv'
    if not param_file.exists():
        logging.warning(f"{param_file} not found. Using default seasons {DEFAULT_SEASONS}.")
        return DEFAULT_SEASONS
    df_p = pd.read_csv(param_file)
    params = dict(zip(df_p['parameter_name'], df_p['value']))
    value = params.get('correlation_seasons', ', '.join(DEFAULT_SEASONS))
    return [s.strip() for s in str(value).split(',')]


def parse_param_column(col, seasons):
    """Split a correlation column name into (parameter season, parameter group label).

    'Winter_2_WTEMP'        -> ('Winter', 'Bottom WTEMP')
    'Spring_Stratification' -> ('Spring', 'Stratification')
    Columns without a recognised season prefix are returned as ('Other', col).
    """
    parts = col.split('_')
    if parts[0] not in seasons or len(parts) < 2:
        return 'Other', col.replace('_', ' ')
    param_season = parts[0]
    if parts[1] in LAYER_NAMES and len(parts) >= 3:
        label = '_'.join(parts[2:])
        label = NUTRIENT_LABELS.get(label, label).replace('_', ' ')
        return param_season, f"{LAYER_NAMES[parts[1]]} {label}"
    return param_season, '_'.join(parts[1:]).replace('_', ' ')


def build_long_table(corr_df, seasons):
    """Convert a wide station x parameter correlation table into long format with p-values."""
    r_cols = [c for c in corr_df.columns if not c.endswith('_pval') and not c.endswith('_n')]
    records = []
    for col in r_cols:
        param_season, group = parse_param_column(col, seasons)
        pval_col = f"{col}_pval"
        pvals = corr_df[pval_col] if pval_col in corr_df.columns else pd.Series(np.nan, index=corr_df.index)
        records.append(pd.DataFrame({
            'zettaicode': corr_df.index,
            'Column': col,
            'Param_Season': param_season,
            'Parameter': group,
            'Pearson_r': corr_df[col].values,
            'P_Value': pvals.values,
        }))
    if not records:
        return pd.DataFrame(columns=['zettaicode', 'Column', 'Param_Season', 'Parameter', 'Pearson_r', 'P_Value'])
    return pd.concat(records, ignore_index=True)


def ordered_unique(values):
    """Unique values preserving first-appearance order (keeps the process01 parameter order)."""
    return list(dict.fromkeys(values))


def season_legend_handles(season_order):
    return [Patch(facecolor=SEASON_COLORS.get(s, 'gray'), edgecolor='black', label=s) for s in season_order]


def plot_distribution(long_tables, season_order, title, output_path):
    """Boxplots of r per parameter group (x) with one box per parameter season (hue)."""
    group_order = ordered_unique(pd.concat(long_tables.values())['Parameter'])
    fig_width = max(18, 1.3 * len(group_order) + 4)
    fig, axes = plt.subplots(2, 1, figsize=(fig_width, 14), sharex=True)
    fig.suptitle(title, fontsize=28)

    palette = {s: SEASON_COLORS.get(s, 'gray') for s in season_order}
    for ax, (pc_name, long_df) in zip(axes, long_tables.items()):
        plot_df = long_df.dropna(subset=['Pearson_r'])
        if plot_df.empty:
            ax.text(0.5, 0.5, f'No valid {pc_name} correlations', transform=ax.transAxes, ha='center')
            continue
        sns.boxplot(
            data=plot_df, x='Parameter', y='Pearson_r', hue='Param_Season',
            order=group_order, hue_order=season_order, palette=palette,
            fliersize=2, linewidth=0.8, ax=ax
        )
        ax.axhline(0, color='gray', linestyle='--')
        ax.set_title(f'Distribution of {pc_name} Correlations by Station')
        ax.set_ylabel('Pearson r')
        ax.set_xlabel('')
        ax.set_ylim(-1.1, 1.1)
        for i in range(1, len(group_order)):
            ax.axvline(i - 0.5, color='lightgray', linewidth=0.6, zorder=0)
        if ax.get_legend() is not None:
            ax.get_legend().remove()

    axes[-1].set_xticks(range(len(group_order)))
    axes[-1].set_xticklabels(group_order, rotation=45, ha='right')
    axes[0].legend(handles=season_legend_handles(season_order), title='Parameter season',
                   loc='upper left', bbox_to_anchor=(1.005, 1.0))

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()


def count_significant(long_df):
    """Count stations with significant positive / negative correlations per parameter permutation."""
    sig = long_df.dropna(subset=['Pearson_r', 'P_Value'])
    sig = sig[sig['P_Value'] < SIG_LEVEL]
    counts = sig.assign(
        Positive=(sig['Pearson_r'] > 0).astype(int),
        Negative=(sig['Pearson_r'] < 0).astype(int)
    ).groupby(['Parameter', 'Param_Season'])[['Positive', 'Negative']].sum()
    return counts


def plot_significance_counts(long_tables, season_order, title, output_path):
    """Diverging grouped bars: negative counts to the left, positive to the right, one bar per season."""
    group_order = ordered_unique(pd.concat(long_tables.values())['Parameter'])
    n_seasons = len(season_order)
    bar_h = 0.8 / n_seasons
    fig_height = max(8, 0.55 * len(group_order) + 3)
    fig, axes = plt.subplots(1, 2, figsize=(20, fig_height), sharey=True)
    fig.suptitle(title, fontsize=28)

    # Pre-calculate totals across ALL PCs to ensure shared sorting
    all_counts = count_significant(pd.concat(long_tables.values()))
    overall_totals = all_counts.sum(axis=1).groupby(level='Parameter').sum().reindex(group_order).fillna(0)
    sorted_groups = overall_totals.sort_values(ascending=True).index.tolist()
    y_base = np.arange(len(sorted_groups))

    for ax, (pc_name, long_df) in zip(axes, long_tables.items()):
        counts = count_significant(long_df)

        for j, param_season in enumerate(season_order):
            offset = (j - (n_seasons - 1) / 2) * bar_h
            pos = [counts['Positive'].get((g, param_season), 0) for g in sorted_groups]
            neg = [counts['Negative'].get((g, param_season), 0) for g in sorted_groups]
            color = SEASON_COLORS.get(param_season, 'gray')
            ax.barh(y_base + offset, pos, height=bar_h, color=color, edgecolor='black', linewidth=0.3)
            ax.barh(y_base + offset, [-n for n in neg], height=bar_h, color=color, edgecolor='black',
                    linewidth=0.3, hatch='///', alpha=0.75)

        ax.axvline(0, color='black', linewidth=1)
        ax.set_yticks(y_base)
        ax.set_yticklabels(sorted_groups)
        for y in y_base[:-1]:
            ax.axhline(y + 0.5, color='lightgray', linewidth=0.6, zorder=0)
        lim = max(1, np.abs(ax.get_xlim()).max())
        ax.set_xlim(-lim, lim)
        ax.set_title(f'{pc_name}')

    axes[0].set_ylabel('Parameter')
    fig.supxlabel('Number of significant stations  (negative r ←  |  → positive r)', y=-0.02)
    handles = season_legend_handles(season_order) + [
        Patch(facecolor='white', edgecolor='black', label='Positive (r > 0)'),
        Patch(facecolor='white', edgecolor='black', hatch='///', label='Negative (r < 0)'),
    ]
    axes[1].legend(handles=handles, title=f'Parameter season / sign (p < {SIG_LEVEL})',
                   loc='upper left', bbox_to_anchor=(1.01, 1.0))

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    parser.add_argument('--data_type', required=True, choices=['env', 'nutr'])
    args = parser.parse_args()
    
    target_region = args.target_region
    season = args.season
    layer = args.layer
    data_type = args.data_type
    region_slug = target_region.replace(' ', '_')
    
    logging.info(f"Running process31 for {data_type} in {target_region}")
    
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    
    pc1_path = subset_dir / f'pca_{data_type}_corr_pc1.csv'
    pc2_path = subset_dir / f'pca_{data_type}_corr_pc2.csv'
    
    if not pc1_path.exists() or not pc2_path.exists():
        logging.warning(f"Correlation files not found for {target_region} {season} {layer}. Skipping.")
        return
        
    corr_df_pc1 = pd.read_csv(pc1_path, dtype={'zettaicode': str}).set_index('zettaicode')
    corr_df_pc2 = pd.read_csv(pc2_path, dtype={'zettaicode': str}).set_index('zettaicode')
    
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE, columns=['zettaicode', 'watermass_name'])
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    if target_region:
        valid_stations = merged_df[merged_df['watermass_name'] == target_region]['zettaicode'].unique()
        corr_df_pc1 = corr_df_pc1[corr_df_pc1.index.isin(valid_stations)]
        corr_df_pc2 = corr_df_pc2[corr_df_pc2.index.isin(valid_stations)]
        
    if corr_df_pc1.empty or corr_df_pc2.empty:
        logging.warning(f"No valid stations found for {target_region}")
        return

    seasons = load_correlation_seasons()
    long_tables = {
        'PC1': build_long_table(corr_df_pc1, seasons),
        'PC2': build_long_table(corr_df_pc2, seasons),
    }
    present = set(pd.concat(long_tables.values())['Param_Season'])
    season_order = [s for s in seasons if s in present] + (['Other'] if 'Other' in present else [])

    for s in season_order:
        filtered_tables = {}
        for pc, df in long_tables.items():
            filtered_tables[pc] = df[df['Param_Season'] == s].copy()
            
        # Skip if no data for this season
        if pd.concat(filtered_tables.values()).empty:
            continue
            
        subset_label = f"DO PCA subset: {season} {layer} | Parameters: {s} | Data: {data_type}"

        # 1. Distribution Boxplot
        plot_distribution(
            filtered_tables, [s],
            f"Environmental Factor PCA Correlation Distribution - {target_region}\n({subset_label})",
            OUTPUT_DIR / f'correlation_distribution_{data_type}_{region_slug}_{season}_{layer}_{s}.png'
        )

        # 2. Significant Diverging Bar Chart
        plot_significance_counts(
            filtered_tables, [s],
            f"Significant PCA Correlations Count - {target_region}\n({subset_label})",
            OUTPUT_DIR / f'correlation_significance_counts_{data_type}_{region_slug}_{season}_{layer}_{s}.png'
        )

if __name__ == '__main__':
    main()

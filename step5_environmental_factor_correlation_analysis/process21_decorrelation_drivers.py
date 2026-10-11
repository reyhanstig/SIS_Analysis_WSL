# -*- coding: utf-8 -*-
import argparse
import sys
from pathlib import Path
import os
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
import seaborn as sns
import gsw
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score, LeaveOneOut
from sklearn.inspection import permutation_importance
import yaml

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

project_root = CURRENT_SCRIPT.parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
if str(project_root / 'scripts') not in sys.path:
    sys.path.append(str(project_root / 'scripts'))

from utils.paths import ProjectPaths

sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)

def get_climatology(df, param, season, saisuipoin=None):
    mask = df['season'] == season
    if saisuipoin is not None:
        mask &= df['saisuipoin'] == saisuipoin
    return pd.to_numeric(df.loc[mask, param], errors='coerce').groupby(df.loc[mask, 'zettaicode']).mean()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    args = parser.parse_args()
    
    season = args.season
    layer = args.layer
    
    logging.info(f"Running process21_decorrelation_drivers for {season} {layer}")
    
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)

    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    decorr_path = subset_dir / 'stations_decorrelation_scale.csv'
    
    if not decorr_path.exists():
        logging.error(f"Decorrelation scale file not found: {decorr_path}")
        sys.exit(1)
        
    decorr_df = pd.read_csv(decorr_path)
    if 'Station_ID' in decorr_df.columns:
        decorr_df['zettaicode'] = decorr_df['Station_ID'].astype(str).str.zfill(8)

    from process01_data_integrity_and_correlation import MatrixBuilder, build_permutation_matrices

    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    builder = MatrixBuilder(merged_df, stations)
    
    corr_params_df = pd.read_csv(CURRENT_SCRIPT.parent / 'step5_correlation_parameters.csv')
    param_file = CURRENT_SCRIPT.parent / 'step5_parameter.csv'
    df_p = pd.read_csv(param_file) if param_file.exists() else pd.DataFrame(columns=['parameter_name', 'value'])
    params = dict(zip(df_p['parameter_name'], df_p['value'])) if not df_p.empty else {}
    corr_seasons = [s.strip() for s in str(params.get('correlation_seasons', 'Spring, Summer, Autumn, Winter')).split(',')]
    
    matrices_env, names_env = build_permutation_matrices(builder, corr_params_df, 'env', corr_seasons)
    matrices_nutr, names_nutr = build_permutation_matrices(builder, corr_params_df, 'nutr', corr_seasons)
    
    all_names = names_env + names_nutr
    all_matrices = matrices_env + matrices_nutr
    
    result_df = stations.copy()
    param_cols = []
    
    # Calculate the climatology (mean over all years) for each permutation
    for name, mat in zip(all_names, all_matrices):
        col_name = f"Mean_{name}"
        result_df[col_name] = mat.mean(axis=0)
        param_cols.append(col_name)

    decorr_df = decorr_df.set_index('zettaicode')
    if 'Decorrelation_Scale_km' in decorr_df.columns:
        result_df = result_df.join(decorr_df[['Decorrelation_Scale_km']].rename(columns={'Decorrelation_Scale_km': 'decorrelation_scale'}))
    elif 'decorrelation_scale' in decorr_df.columns:
        result_df = result_df.join(decorr_df[['decorrelation_scale']])
    elif 'dx' in decorr_df.columns:
        result_df = result_df.join(decorr_df[['dx']].rename(columns={'dx': 'decorrelation_scale'}))

    model_df = result_df[param_cols + ['decorrelation_scale']].dropna()
    X = model_df[param_cols]
    y = model_df['decorrelation_scale']

    if len(X) < 10:
        logging.warning("Not enough samples for Random Forest Regression.")
        sys.exit(0)

    rf = RandomForestRegressor(
        n_estimators=500, max_depth=None, min_samples_split=5,
        min_samples_leaf=2, random_state=42, n_jobs=-1
    )
    rf.fit(X, y)

    perm_result = permutation_importance(rf, X, y, n_repeats=30, random_state=42, n_jobs=-1)
    perm_importance = pd.Series(perm_result.importances_mean, index=param_cols, name='Permutation_Importance')
    importance_df = pd.DataFrame({'Permutation_Importance': perm_importance}).sort_values('Permutation_Importance', ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    importance_df['Permutation_Importance'].sort_values().plot.barh(
        ax=axes[0], color='steelblue', edgecolor='black', linewidth=0.5
    )
    axes[0].set_xlabel('Permutation Importance')
    axes[0].set_title('Feature Importance (Permutation)')
    axes[0].axvline(x=0, color='grey', linestyle='--', linewidth=0.8)

    y_pred = rf.predict(X)
    axes[1].scatter(y, y_pred, alpha=0.6, edgecolors='black', linewidth=0.5, color='coral')
    lims = [min(y.min(), y_pred.min()) - 1, max(y.max(), y_pred.max()) + 1]
    axes[1].plot(lims, lims, 'k--', linewidth=1, label='1:1 line')
    axes[1].set_xlabel('Observed Decorrelation Scale (km)')
    axes[1].set_ylabel('Predicted Decorrelation Scale (km)')
    axes[1].set_title(f'Predicted vs Observed  (Training R²={rf.score(X, y):.3f})')
    axes[1].legend()
    axes[1].set_xlim(lims)
    axes[1].set_ylim(lims)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f'decorrelation_drivers_rf_{season}_{layer}.png', bbox_inches='tight', dpi=300)
    plt.close()

if __name__ == '__main__':
    main()

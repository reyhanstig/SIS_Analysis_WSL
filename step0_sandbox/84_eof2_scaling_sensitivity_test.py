# -*- coding: utf-8 -*-
"""
Sandbox Script 84: Is the raw-vs-standardized disagreement of EOF2 a variance-weighting artefact?
Notebook 83 found that EOF2 often changes completely between raw (covariance) and standardized
(correlation) PCA. The claim tested here: "if EOF2 changes completely when the stations are rescaled,
it is probably not a robust physical pattern; it may mostly reflect which stations have large variance."

Five tests per dataset (Seto Inland Sea pooled, plus each division), all using the pipeline logic of
step4 process01 / process11:
  A. Scaling continuum: station scaling sd**alpha, alpha = 0 (raw) ... 1 (standardized). Does EOF2 drift
     smoothly or jump? Tracks the eigenvalue ratio lambda2/lambda3 along the way.
  B. North et al. (1982) rule of thumb: are the neighbouring eigenvalues of EOF2 separated beyond sampling error?
  C. Bootstrap over years: how stable is EOF2 within each mode, and across modes, under sampling noise?
  D. Variance-assignment shuffle: keep the correlation structure but permute the station variances. Does the
     real station-variance pattern disturb EOF2 more than random variances of the same magnitude do?
  E. Spatial coherence (Moran's I on k-nearest-neighbour stations) of the EOF loadings in each mode.
Parameters are read from 84_eof2_scaling_sensitivity_test_parameters.csv (defaults are written if missing).
"""

import sys
import shutil
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

plt.style.use(str(PROJECT_ROOT / 'project_style.mplstyle'))

from utils.paths import ProjectPaths
from utils.data_loader import load_and_process_data

# Directories
STEP_DIR = "step0_sandbox"
SCRIPT_NAME = "84_eof2_scaling_sensitivity_test"
OUTPUT_DIR = ProjectPaths.FIGURES_DIR / STEP_DIR / SCRIPT_NAME
PARAM_FILE = Path(__file__).resolve().parent / f"{SCRIPT_NAME}_parameters.csv"
DECORR_DIR = ProjectPaths.PROCESSED_DATA_DIR / "step3_decorrelation_scale_analysis" / "process11_calculate_decorrelation_scale_per_bay"
SETO_NAME = "Seto Inland Sea (all)"

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

DEFAULT_PARAMS = {
    'n_bootstrap': (500, 'int', 'Bootstrap resamples of the years (test C)'),
    'n_variance_shuffles': (500, 'int', 'Station-variance permutations (test D)'),
    'n_moran_permutations': (999, 'int', 'Permutations for the Moran I p-value (test E)'),
    'moran_k_neighbours': (4, 'int', 'Nearest neighbours used for the Moran I weights'),
    'n_alpha_steps': (11, 'int', 'Number of scaling exponents between 0 (raw) and 1 (standardized)'),
    'stable_threshold': (0.85, 'float', 'Tucker congruence regarded as "same pattern" (notebook 83 uses 0.85 as fair)'),
    'random_seed': (42, 'int', 'Seed for all random draws'),
}


# ----------------------------------------------------------------------------- inputs
def load_params():
    """Load parameters (written with defaults if the CSV is missing) plus season/layer/divisions from steps 1 and 3."""
    if not PARAM_FILE.exists():
        pd.DataFrame([{'parameter_name': k, 'value': v[0], 'type': v[1], 'description': v[2]}
                      for k, v in DEFAULT_PARAMS.items()]).to_csv(PARAM_FILE, index=False)
        logging.info(f"Wrote default parameters to {PARAM_FILE}")
    df = pd.read_csv(PARAM_FILE)
    params = {r['parameter_name']: (int(r['value']) if r['type'] == 'int' else float(r['value'])) for _, r in df.iterrows()}

    def read_csv_params(path):
        return dict(zip(*pd.read_csv(path)[['parameter_name', 'value']].values.T)) if path.exists() else {}

    s1 = read_csv_params(PROJECT_ROOT / "step1_data_processing_cleaning" / "step1_parameter.csv")
    s3 = read_csv_params(PROJECT_ROOT / "step3_decorrelation_scale_analysis" / "step3_parameter.csv")
    params['season'] = s1.get('season', 'Summer')
    params['layer'] = s1.get('layer', 'bottom')
    params['divisions'] = [d.strip() for d in str(s3.get('divisions', 'Seto Inland Sea, Tokyo Bay, Ise Mikawa Bay, Osaka Bay')).split(',')]
    return params


def check_inputs(paths):
    missing = [p for p in paths if not p.exists()]
    for p in missing:
        logging.warning(f"Missing input file: {p}")
    return not missing


def gaussian_weight(distance, scale):
    return np.exp(-(distance ** 2) / (2 * scale ** 2))


def interpolate_missing_do(yearly_do_df, decorrelation_df, dist_matrix, min_weight=0.01):
    """Verbatim logic of process11_calculate_pca_explained_variance_per_bay_raw.interpolate_missing_do."""
    search_radius_factor = 2.0
    interpolated_df = yearly_do_df.copy()
    common_stations = list(set(yearly_do_df.index) & set(decorrelation_df.index) & set(dist_matrix.index))
    for year in yearly_do_df.columns:
        for station in common_stations:
            if not pd.isna(yearly_do_df.loc[station, year]):
                continue
            scale = decorrelation_df.loc[station, 'Decorrelation_Scale_km']
            if pd.isna(scale) or scale <= 0:
                continue
            search_radius = search_radius_factor * scale
            valid_stations = yearly_do_df.index[~pd.isna(yearly_do_df[year])].tolist()
            neighbors = [s for s in valid_stations if s in common_stations and s != station]
            if len(neighbors) == 0:
                continue
            distances = dist_matrix.loc[station, neighbors]
            within_radius = distances[distances <= search_radius]
            if len(within_radius) == 0:
                continue
            neighbors_in_radius = within_radius.index.tolist()
            dist_vals = dist_matrix.loc[station, neighbors_in_radius].values
            do_vals = yearly_do_df.loc[neighbors_in_radius, year].values
            weight_vals = gaussian_weight(dist_vals, scale)
            valid_mask = weight_vals > min_weight
            if valid_mask.sum() == 0:
                continue
            interpolated_df.loc[station, year] = (do_vals[valid_mask] * weight_vals[valid_mask]).sum() / weight_vals[valid_mask].sum()
    mean_fallback = interpolated_df.mean(axis=1)
    for col in interpolated_df.columns:
        interpolated_df[col] = interpolated_df[col].fillna(mean_fallback)
    return interpolated_df


def load_division_matrix(division, merged_gdf, yearly_do_df, dist_matrix_km):
    """Stations x years matrix for one division, as in process11.main(); None if inputs are missing."""
    db_division = 'Ise Bay' if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay'] else division
    stations = merged_gdf[(merged_gdf['watermass_name'] == db_division) | (merged_gdf['division'] == db_division)]['zettaicode'].unique()
    ids = [str(s).zfill(8) for s in stations]
    df_div = yearly_do_df[yearly_do_df.index.isin(ids)].copy()
    if df_div.empty:
        logging.warning(f"{division}: no stations in yearly_do_df, skipped")
        return None
    slug = division.replace(' ', '_').lower()
    decorr_file = DECORR_DIR / slug / f"{slug}_decorrelation_scale.csv"
    if division == 'Ise Bay' and not decorr_file.exists():
        slug = 'ise_mikawa_bay'
        decorr_file = DECORR_DIR / slug / f"{slug}_decorrelation_scale.csv"
    if not decorr_file.exists():
        logging.warning(f"{division}: decorrelation scale file not found, skipped")
        return None
    decorr = pd.read_csv(decorr_file, index_col='Station_ID')
    decorr.index = decorr.index.astype(str).str.zfill(8)
    mat = interpolate_missing_do(df_div, decorr, dist_matrix_km)
    mat = mat.fillna(mat.mean(axis=0))
    return mat if len(mat) >= 4 else None


# ----------------------------------------------------------------------------- PCA helpers
def eofs(X, alpha, k=3):
    """First k eigenvalues and EOFs of years x stations X after scaling each station by its std**alpha.
    alpha = 0 is the raw (covariance) PCA, alpha = 1 the standardized (correlation) PCA."""
    Xc = X - X.mean(axis=0)
    if alpha:
        sd = Xc.std(axis=0, ddof=1)
        sd[sd == 0] = 1.0  # zero-variance station contributes nothing, as in StandardScaler
        Xc = Xc / sd ** alpha
    _, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    k = min(k, len(S))
    return S[:k] ** 2 / (len(X) - 1), Vt[:k]


def phi(a, b):
    """Absolute Tucker congruence (cosine similarity, sign-free)."""
    return float(abs(a @ b) / np.sqrt((a @ a) * (b @ b)))


def north_separation(eig, n_years):
    """Gap of lambda2 to its nearest neighbour divided by its sampling error lambda2*sqrt(2/n). Above 1 = separated."""
    err = eig[1] * np.sqrt(2.0 / n_years)
    return float(min(eig[0] - eig[1], eig[1] - eig[2]) / err)


# ----------------------------------------------------------------------------- tests
def test_alpha_continuum(X, alphas):
    """A. EOF2 congruence to the raw and standardized EOF2 and lambda2/lambda3 along the scaling exponent."""
    _, V0 = eofs(X, 0.0)
    _, V1 = eofs(X, 1.0)
    rows = []
    for a in alphas:
        eig, V = eofs(X, a)
        rows.append({'alpha': a, 'phi_to_raw': phi(V[1], V0[1]), 'phi_to_std': phi(V[1], V1[1]), 'eig_ratio_2_3': eig[1] / eig[2]})
    df = pd.DataFrame(rows)
    # largest change of EOF2 between neighbouring exponents: a large value means an abrupt switch
    df.attrs['max_step'] = float((1 - df['phi_to_raw']).diff().abs().max())
    return df


def test_bootstrap(X, B, rng):
    """C. Resample years; EOF2 stability within each mode, and raw-vs-standardized agreement per resample."""
    n = X.shape[0]
    _, R = eofs(X, 0.0)
    _, S = eofs(X, 1.0)
    out = {k: [] for k in ['raw_e1', 'raw_e2', 'std_e1', 'std_e2', 'cross_e1', 'cross_e2']}
    for _ in range(B):
        idx = rng.integers(0, n, n)
        _, Rb = eofs(X[idx], 0.0)
        _, Sb = eofs(X[idx], 1.0)
        out['raw_e1'].append(phi(Rb[0], R[0])); out['raw_e2'].append(phi(Rb[1], R[1]))
        out['std_e1'].append(phi(Sb[0], S[0])); out['std_e2'].append(phi(Sb[1], S[1]))
        out['cross_e1'].append(phi(Rb[0], Sb[0])); out['cross_e2'].append(phi(Rb[1], Sb[1]))
    return {k: np.array(v) for k, v in out.items()}


def test_variance_shuffle(X, P, rng):
    """D. Same correlation structure, station variances randomly reassigned: congruence of raw vs standardized EOF1/EOF2."""
    Xc = X - X.mean(axis=0)
    sd = Xc.std(axis=0, ddof=1)
    sd[sd == 0] = 1.0
    Z = Xc / sd
    _, V1 = eofs(Z, 0.0)  # standardized EOFs (Z already has unit variance)
    obs = [phi(eofs(X, 0.0)[1][i], V1[i]) for i in (0, 1)]
    sims = np.zeros((P, 2))
    for p in range(P):
        _, V = eofs(Z * rng.permutation(sd), 0.0)
        sims[p] = [phi(V[0], V1[0]), phi(V[1], V1[1])]
    return obs, sims


def haversine_km(lat, lon):
    """Pairwise great-circle distances (km) between stations given latitude/longitude in degrees."""
    la, lo = np.radians(lat)[:, None], np.radians(lon)[:, None]
    a = np.sin((la - la.T) / 2) ** 2 + np.cos(la) * np.cos(la.T) * np.sin((lo - lo.T) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def knn_weights(D, k):
    """Row-standardised k-nearest-neighbour weights from a station distance matrix."""
    n = D.shape[0]
    D = D.copy()
    np.fill_diagonal(D, np.inf)
    W = np.zeros((n, n))
    for i in range(n):
        W[i, np.argsort(D[i])[:k]] = 1.0 / k
    return W


def morans_i(vals, W, nperm, rng):
    """E. Moran's I of the loadings and its one-sided permutation p-value (positive spatial autocorrelation)."""
    z = vals - vals.mean()
    denom = (z ** 2).sum()
    obs = float(z @ (W @ z) / denom)
    perms = np.array([(zp @ (W @ zp)) / denom for zp in (rng.permutation(z) for _ in range(nperm))])
    return obs, float((1 + (perms >= obs).sum()) / (nperm + 1))


# ----------------------------------------------------------------------------- per-dataset driver
def analyse(name, mat, station_coords, params, rng):
    ids = [s for s in mat.index if s in station_coords.index]
    mat = mat.loc[ids]
    X = mat.T.values.astype(float)  # years x stations
    n_years, n_st = X.shape
    logging.info(f"{name}: {n_st} stations x {n_years} years")

    eig_r, V_r = eofs(X, 0.0)
    eig_s, V_s = eofs(X, 1.0)
    sd = X.std(axis=0, ddof=1)
    cross = {i: phi(V_r[i], V_s[i]) for i in (0, 1)}
    cross_best3 = max(phi(V_r[1], V_s[j]) for j in range(3))

    cont = test_alpha_continuum(X, np.linspace(0, 1, int(params['n_alpha_steps'])))
    boot = test_bootstrap(X, int(params['n_bootstrap']), rng)
    obs, sims = test_variance_shuffle(X, int(params['n_variance_shuffles']), rng)

    D = haversine_km(station_coords.loc[ids, 'latitude'].values, station_coords.loc[ids, 'longitude'].values)
    W = knn_weights(D, min(int(params['moran_k_neighbours']), n_st - 1))
    moran = {}
    for mode, V in [('raw', V_r), ('std', V_s)]:
        for i in (0, 1):
            moran[f'moran_{mode}_e{i + 1}'], moran[f'moran_p_{mode}_e{i + 1}'] = morans_i(V[i], W, int(params['n_moran_permutations']), rng)

    top_q = sd >= np.quantile(sd, 0.75)
    row = {
        'dataset': name, 'n_stations': n_st, 'station_std_cv': sd.std(ddof=1) / sd.mean(),
        'cross_phi_e1': cross[0], 'cross_phi_e2': cross[1], 'cross_phi_e2_best_of_3': cross_best3,
        'alpha_max_step_e2': cont.attrs['max_step'],
        'north_sep_raw': north_separation(eig_r, n_years), 'north_sep_std': north_separation(eig_s, n_years),
        'boot_stab_raw_e1': np.median(boot['raw_e1']), 'boot_stab_raw_e2': np.median(boot['raw_e2']),
        'boot_stab_std_e1': np.median(boot['std_e1']), 'boot_stab_std_e2': np.median(boot['std_e2']),
        'boot_cross_e2_median': np.median(boot['cross_e2']),
        'shuffle_phi_e2_obs': obs[1], 'shuffle_phi_e2_median': np.median(sims[:, 1]),
        'shuffle_p_e2': float((sims[:, 1] <= obs[1]).mean()),
        'shuffle_phi_e1_obs': obs[0], 'shuffle_phi_e1_median': np.median(sims[:, 0]),
        'spearman_std_absEOF2_raw': spearmanr(sd, np.abs(V_r[1]))[0], 'spearman_std_absEOF2_std': spearmanr(sd, np.abs(V_s[1]))[0],
        'top_quartile_var_share_raw_e2': float((V_r[1][top_q] ** 2).sum() / (V_r[1] ** 2).sum()),
        'top_quartile_var_share_std_e2': float((V_s[1][top_q] ** 2).sum() / (V_s[1] ** 2).sum()),
        **moran,
    }
    thr = params['stable_threshold']
    within_min = min(row['boot_stab_raw_e2'], row['boot_stab_std_e2'])
    if row['cross_phi_e2'] >= thr:
        row['eof2_class'] = 'robust'
    elif within_min < thr:
        row['eof2_class'] = 'sampling-limited'
    elif cross_best3 >= thr:
        row['eof2_class'] = 'reordered'
    else:
        row['eof2_class'] = 'weighting-dependent'
    return row, cont, sims


# ----------------------------------------------------------------------------- figures
def plot_continuum(conts, classes):
    n = len(conts)
    ncol = 4
    fig, axes = plt.subplots(int(np.ceil(n / ncol)), ncol, figsize=(4.6 * ncol, 3.6 * int(np.ceil(n / ncol))), squeeze=False)
    for ax, (name, c) in zip(axes.ravel(), conts.items()):
        ax.plot(c['alpha'], c['phi_to_raw'], color='tab:blue', marker='o', ms=3, label='to raw EOF2')
        ax.plot(c['alpha'], c['phi_to_std'], color='darkgoldenrod', marker='s', ms=3, label='to standardized EOF2')
        ax.set_ylim(-0.02, 1.02)
        ax2 = ax.twinx()
        ax2.plot(c['alpha'], c['eig_ratio_2_3'], color='grey', ls='--', lw=1)
        ax2.axhline(1, color='grey', lw=0.5)
        ax2.set_ylim(bottom=0.9)
        ax.set_title(f"{name}\n[{classes[name]}]", fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.4)
    for ax in axes.ravel()[n:]:
        ax.axis('off')
    axes[0, 0].legend(fontsize=7, loc='lower center')
    fig.supxlabel('Scaling exponent alpha (0 = raw, 1 = standardized)')
    fig.supylabel('|congruence| of EOF2; dashed = lambda2/lambda3 (right axis)')
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / 'eof2_alpha_continuum.png', bbox_inches='tight', dpi=300)
    plt.close(fig)


def plot_summary(df, sims_all):
    fig, axes = plt.subplots(1, 3, figsize=(21, 6.5))
    plt.rcParams.update({'axes.titlesize': 12, 'axes.labelsize': 11, 'xtick.labelsize': 9, 'ytick.labelsize': 9})
    cols = {'robust': 'tab:green', 'reordered': 'tab:orange', 'weighting-dependent': 'tab:red', 'sampling-limited': 'tab:purple'}
    ax = axes[0]
    for _, r in df.iterrows():
        ax.scatter(r['cross_phi_e2'], min(r['boot_stab_raw_e2'], r['boot_stab_std_e2']), color=cols[r['eof2_class']], s=60, edgecolors='k')
        ax.annotate(r['dataset'].replace(' (all)', ''), (r['cross_phi_e2'], min(r['boot_stab_raw_e2'], r['boot_stab_std_e2'])), fontsize=7, xytext=(3, 3), textcoords='offset points')
    ax.plot([0, 1], [0, 1], 'k--', lw=0.8)
    ax.set_xlabel('Raw-vs-standardized |φ| of EOF2'); ax.set_ylabel('Bootstrap EOF2 stability, worse mode')
    ax.set_title('Mode disagreement vs sampling noise', fontsize=12)
    ax.handles = [ax.scatter([], [], color=c, edgecolors='k', label=k) for k, c in cols.items()]
    ax.legend(handles=ax.handles, fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.4)

    ax = axes[1]
    y = np.arange(len(df))
    for i, (name, s) in enumerate(sims_all.items()):
        ax.plot(np.percentile(s[:, 1], [5, 95]), [i, i], color='grey', lw=3, alpha=0.6)
    ax.scatter(df['shuffle_phi_e2_obs'], y, color='k', zorder=3, label='observed (real variances)')
    ax.scatter(df['shuffle_phi_e2_median'], y, color='tab:blue', marker='|', s=200, zorder=3, label='median, shuffled variances')
    ax.set_yticks(y); ax.set_yticklabels(df['dataset'].str.replace(' (all)', '', regex=False), fontsize=8)
    ax.set_xlabel('Raw-vs-standardized |φ| of EOF2'); ax.set_title('Real vs shuffled variances (grey: 5-95%)', fontsize=12)
    ax.legend(fontsize=8); ax.grid(True, linestyle='--', alpha=0.4)

    ax = axes[2]
    ax.scatter(df['moran_raw_e2'], df['moran_std_e2'], c=[cols[c] for c in df['eof2_class']], s=60, edgecolors='k')
    for _, r in df.iterrows():
        ax.annotate(r['dataset'].replace(' (all)', ''), (r['moran_raw_e2'], r['moran_std_e2']), fontsize=7, xytext=(3, 3), textcoords='offset points')
    ax.plot([-0.3, 1], [-0.3, 1], 'k--', lw=0.8); ax.axhline(0, color='grey', lw=0.5); ax.axvline(0, color='grey', lw=0.5)
    ax.set_xlabel("Moran's I of raw EOF2"); ax.set_ylabel("Moran's I of standardized EOF2")
    ax.set_title('Spatial coherence of EOF2', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.4)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / 'eof2_scaling_sensitivity_summary.png', bbox_inches='tight', dpi=300)
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def main():
    params = load_params()
    subset_dir = ProjectPaths.get_subset_dir(params['season'], params['layer'])
    inputs = [subset_dir / "interpolated_do_df.csv", subset_dir / "yearly_do_df.csv", ProjectPaths.PROCESSED_DATA_DIR / "dist_matrix_km.csv"]
    if not check_inputs(inputs):
        logging.warning("Skipping script 84: required inputs are missing.")
        return

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def read_matrix(path):
        df = pd.read_csv(path, index_col=0)
        df.index = df.index.astype(str).str.zfill(8)
        return df

    interpolated_do_df, yearly_do_df = read_matrix(inputs[0]), read_matrix(inputs[1])
    dist_matrix_km = read_matrix(inputs[2])
    dist_matrix_km.columns = dist_matrix_km.columns.astype(str).str.zfill(8)
    merged_gdf = load_and_process_data(force_reload=False)
    station_coords = merged_gdf[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').copy()
    station_coords.index = station_coords['zettaicode'].astype(str).str.zfill(8)

    # Same fill as process01 (fills with the per-year mean over stations; the pipeline comment calls it "temporal mean")
    n_nan = int(interpolated_do_df.isna().sum().sum())
    logging.info(f"NaNs in the pooled Seto matrix before the pipeline fill: {n_nan}")
    datasets = {SETO_NAME: interpolated_do_df.fillna(interpolated_do_df.mean(axis=0))}

    regions = set()
    for div in params['divisions']:
        if div == 'Seto Inland Sea':
            regions.update(merged_gdf[merged_gdf['watermass_name'] == 'Seto Inland Sea']['division'].dropna().unique())
        else:
            regions.add(div)
    for division in sorted(regions):
        mat = load_division_matrix(division, merged_gdf, yearly_do_df, dist_matrix_km)
        if mat is not None:
            datasets[division] = mat

    rng = np.random.default_rng(int(params['random_seed']))
    rows, conts, sims_all = [], {}, {}
    for name, mat in datasets.items():
        row, cont, sims = analyse(name, mat, station_coords, params, rng)
        rows.append(row); conts[name] = cont; sims_all[name] = sims
    df = pd.DataFrame(rows)

    df.to_csv(OUTPUT_DIR / 'eof2_scaling_sensitivity_results.csv', index=False)
    pd.concat(conts, names=['dataset']).to_csv(OUTPUT_DIR / 'eof2_alpha_continuum.csv')
    plot_continuum(conts, dict(zip(df['dataset'], df['eof2_class'])))
    plot_summary(df, sims_all)

    # Cross-dataset association of each explanation with the observed disagreement
    pd.set_option('display.width', 250, 'display.max_columns', 40)
    print("\n=== Per-dataset results ===")
    print(df[['dataset', 'n_stations', 'station_std_cv', 'cross_phi_e1', 'cross_phi_e2', 'north_sep_raw', 'north_sep_std',
              'boot_stab_raw_e2', 'boot_stab_std_e2', 'shuffle_phi_e2_obs', 'shuffle_phi_e2_median', 'shuffle_p_e2',
              'moran_raw_e2', 'moran_std_e2', 'eof2_class']].round(2).to_string(index=False))
    print("\n=== Class counts ===")
    print(df['eof2_class'].value_counts().to_string())
    d = df[df['dataset'] != SETO_NAME]
    print("\n=== Cross-dataset Spearman correlations (13 divisions) ===")
    for a, b in [('station_std_cv', 'cross_phi_e2'), ('station_std_cv', 'cross_phi_e1'), ('north_sep_raw', 'boot_stab_raw_e2'),
                 ('north_sep_std', 'boot_stab_std_e2'), ('boot_stab_raw_e2', 'cross_phi_e2'), ('boot_stab_std_e2', 'cross_phi_e2')]:
        r, p = spearmanr(d[a], d[b])
        print(f"{a:>18} vs {b:<18} rho = {r:+.2f} (p = {p:.3f})")
    print(f"\nOutputs written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

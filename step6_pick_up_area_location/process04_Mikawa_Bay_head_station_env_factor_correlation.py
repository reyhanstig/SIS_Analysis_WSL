import pandas as pd
import numpy as np
import logging
import sys
from pathlib import Path
from scipy.stats import linregress
import matplotlib.pyplot as plt
import seaborn as sns
import gsw

# Boilerplate
CURRENT_SCRIPT = Path(__file__).resolve()
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

project_root = CURRENT_SCRIPT.parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
style_path = ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'
if style_path.exists():
    plt.style.use(str(style_path))

def get_ts(df, col, layer, season, station):
    # Special handling for stratification
    if col == 'stratification':
        subset = df[(df['season'] == season) & (df['zettaicode'] == station)].copy()
        if subset.empty: return pd.Series(dtype=float)
        
        salt_col = 'salt2' if 'salt2' in subset.columns else 'salt'
        subset['salt_calc'] = pd.to_numeric(subset[salt_col], errors='coerce')
        subset['wtemp_calc'] = pd.to_numeric(subset['wtemp'], errors='coerce')
        subset['density'] = gsw.rho(subset['salt_calc'], subset['wtemp_calc'], 0) - 1000
        subset['saisuidept'] = pd.to_numeric(subset['saisuidept'], errors='coerce')
        
        surf = subset[subset['saisuipoin'] == 1].groupby('surveyyear')[['density', 'saisuidept']].mean()
        bot = subset[subset['saisuipoin'] == 2].groupby('surveyyear')[['density', 'saisuidept']].mean()
        
        merged = bot.join(surf, lsuffix='_bot', rsuffix='_surf')
        strat = (merged['density_bot'] - merged['density_surf']) / (merged['saisuidept_bot'] - merged['saisuidept_surf']).replace(0, np.nan)
        return strat.dropna()

    subset = df[(df['season'] == season) & (df['saisuipoin'] == layer) & (df['zettaicode'] == station)].copy()
    if subset.empty: return pd.Series(dtype=float)
    
    if col not in subset.columns:
        if col == 'din':
            nh4 = pd.to_numeric(subset['nh4n'], errors='coerce').fillna(0)
            no2 = pd.to_numeric(subset['no2n'], errors='coerce').fillna(0)
            no3 = pd.to_numeric(subset['no3n'], errors='coerce').fillna(0)
            subset['din'] = nh4 + no2 + no3
            all_nan = subset['nh4n'].isna() & subset['no2n'].isna() & subset['no3n'].isna()
            subset.loc[all_nan, 'din'] = np.nan
        else:
            return pd.Series(dtype=float)

    subset[col] = pd.to_numeric(subset[col], errors='coerce')
    return subset.groupby('surveyyear')[col].mean().dropna()

def main():
    target_stations = ['00002355', '00002631']
    
    # Load step 5 parameters
    param_file = project_root / 'step5_environmental_factor_correlation_analysis' / 'step5_ts_parameters.csv'
    if not param_file.exists():
        logging.error(f"Parameter file not found: {param_file}")
        return
    params_df = pd.read_csv(param_file)
    
    logging.info("Loading merged data...")
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    merged_df['zettaicode'] = merged_df['zettaicode'].astype(str).str.zfill(8)
    
    # Filter for target stations early to save memory/time
    merged_df = merged_df[merged_df['zettaicode'].isin(target_stations)].copy()
    
    # Identify target parameter row (Bottom Summer DO)
    target_param_row = params_df[(params_df['col'] == 'do_') & (params_df['layer'] == 2) & (params_df['season'] == 'Summer')]
    if target_param_row.empty:
        logging.error("Target parameter Bottom Summer DO not found in parameters list.")
        return
    target_param = target_param_row.iloc[0]
    
    results = []
    
    for station in target_stations:
        logging.info(f"Processing station {station}...")
        
        target_ts = get_ts(merged_df, target_param['col'], target_param['layer'], target_param['season'], station)
        if target_ts.empty:
            logging.warning(f"No target data (Bottom DO) for station {station}")
            continue
            
        for _, param_row in params_df.iterrows():
            if param_row['title'] == target_param['title']:
                continue
                
            env_ts = get_ts(merged_df, param_row['col'], param_row['layer'], param_row['season'], station)
            if env_ts.empty:
                continue
                
            common_years = target_ts.index.intersection(env_ts.index)
            if len(common_years) < 3:
                continue
                
            y = target_ts.loc[common_years]
            x = env_ts.loc[common_years]
            
            # remove pairs with NA
            valid = y.notna() & x.notna()
            if valid.sum() < 3:
                continue
                
            y = y[valid]
            x = x[valid]
            
            if y.std() == 0 or x.std() == 0:
                continue
                
            slope, intercept, r_value, p_value, std_err = linregress(x, y)
            
            results.append({
                'Station': station,
                'Env_Parameter': param_row['title'],
                'R': r_value,
                'R_squared': r_value**2,
                'p_value': p_value,
                'n': len(x),
                'slope': slope,
                'intercept': intercept
            })
            
            # Plot significant correlations (p < 0.05) or maybe all of them? 
            # We'll plot all of them to allow visual inspection
            fig, ax = plt.subplots(figsize=(7, 6))
            sns.regplot(
                x=x.values, 
                y=y.values, 
                ax=ax, 
                scatter_kws={'s': 80, 'alpha': 0.7, 'edgecolor': 'k', 'color': 'steelblue'},
                line_kws={'color': 'indianred', 'linewidth': 2.5}
            )
            for year, xv, yv in zip(x.index, x.values, y.values):
                ax.annotate(str(int(year)), (xv, yv), xytext=(5, 5), textcoords='offset points', fontsize=10, alpha=0.7)
            
            sig_star = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else ""
            
            ax.set_title(f"Station {station}\n{target_param['title']} vs {param_row['title']}", fontsize=16, fontweight='bold')
            ax.set_xlabel(f"{param_row['title']} [{param_row['unit']}]", fontsize=14)
            ax.set_ylabel(f"{target_param['title']} [{target_param['unit']}]", fontsize=14)
            ax.grid(True, linestyle='--', alpha=0.5)
            
            stats_text = f"$R^2 = {r_value**2:.3f}$\n$p = {p_value:.3e} {sig_star}$\n$n = {len(x)}$"
            props = dict(boxstyle='round', facecolor='whitesmoke', alpha=0.8, edgecolor='gray')
            ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=12,
                    verticalalignment='top', bbox=props)
            
            safe_title = param_row['title'].replace(' ', '_').replace('/', '_')
            station_dir = OUTPUT_DIR / station
            station_dir.mkdir(parents=True, exist_ok=True)
            out_path = station_dir / f"{station}_{safe_title}_corr.png"
            plt.tight_layout()
            plt.savefig(out_path, dpi=300, bbox_inches='tight')
            plt.close(fig)
                
    if results:
        results_df = pd.DataFrame(results)
        # Sort by station and R-squared
        results_df = results_df.sort_values(['Station', 'R_squared'], ascending=[True, False])
        results_csv = PROCESSED_DATA_DIR / "station_correlation_results.csv"
        results_df.to_csv(results_csv, index=False)
        logging.info(f"Correlation results saved to {results_csv}")
    else:
        logging.info("No common data points found for correlations.")

if __name__ == '__main__':
    main()

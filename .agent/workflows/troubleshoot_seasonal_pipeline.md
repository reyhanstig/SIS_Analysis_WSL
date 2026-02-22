---
description: Troubleshoot and verify the seasonal dataset pipeline extension (Stage 1.5 + downstream Stages 2-4)
---

# Troubleshoot Seasonal Pipeline Extension

## Context

The pipeline was extended to support 8 season×layer subsets. The following files were modified:

- `scripts/paths.py` — added `SEASONAL_DATA_DIR`, `get_subset_dir()`, `ensure_subset_dir()`
- `params.yaml` — added `seasonal_subsets.min_periods`
- `dvc.yaml` — added `create_seasonal_datasets` stage; updated `decorrelation`, `interpolation`, `pca_analysis` stages to use `data/processed/seasonal/summer_bottom/` paths
- `notebooks/pipeline/pipeline_summary.md` — documented Stage 1.5 and updated Stages 2–4
- `notebooks/pipeline/02_Create_Seasonal_Datasets.ipynb` — **new** Stage 1.5 notebook
- `notebooks/pipeline/08_Decorrelation_Analysis_v3.ipynb` — modified to accept `subset_dir` parameter
- `notebooks/pipeline/09_Spatial_Interpolation_v2.ipynb` — modified to accept `subset_dir` parameter
- `notebooks/pipeline/10_PCA_Analysis.ipynb` — modified to accept `subset_dir` parameter

The `dist_matrix_km.csv` is **shared** across all subsets (stays at `data/processed/dist_matrix_km.csv`).

## Known Issues

### Issue 1: DVC Symlink Error — outputs "outside of git repository"

**Symptom**: `dvc repro` fails with:
```
ERROR: failed to reproduce 'create_seasonal_datasets': '.../data/processed/seasonal/...' is outside of git repository
```

**Root Cause**: The `data/` directory is a symlink pointing to `/mnt/c/Users/reyha/Documents/SIS_Analysis_Windows/data`, which is outside the git repo root. DVC resolves symlinks and rejects paths outside the repo boundary.

**Diagnosis steps**:
```bash
ls -la /home/reyha/SIS_Analysis_WSL/data
# Expected: data -> /mnt/c/Users/reyha/Documents/SIS_Analysis_Windows/data
```

**Possible fixes** (pick one):
1. **Move data into the repo** and remove the symlink (simplest but changes Windows workflow)
2. **Reverse the symlink direction**: keep real data in the WSL repo, create a symlink on Windows pointing into it
3. **Use `dvc remote`** instead of tracking outputs locally via `outs:` — store them in a DVC remote
4. **Use relative paths** and configure DVC to allow external outputs. Check if `dvc config core.allow_external true` resolves it (may not work for all DVC versions):
   ```bash
   cd /home/reyha/SIS_Analysis_WSL
   conda run -n sis_analysis dvc config core.allow_external true
   conda run -n sis_analysis dvc repro create_seasonal_datasets
   ```

**Note**: This same issue affects the `hypoxia_mapping` stage (`figures/` is also a symlink). Fixing one fixes both.

### Issue 2: Papermill "Passed unknown parameter" Warning

**Symptom**: When running `02_Create_Seasonal_Datasets.ipynb` via `run_pipeline_step.py`:
```
Unable to parse line 2 '...'
Passed unknown parameter: min_periods
```

**Root Cause**: The parameters cell in `02_Create_Seasonal_Datasets.ipynb` contains variables `seasons` and `layers` that are compound types (list/dict). Papermill injects `min_periods` from `params.yaml`, but encounters parse issues with the comment on the same line.

**Fix**: In `02_Create_Seasonal_Datasets.ipynb`, update the parameters cell to separate the comment:
```python
# Parameters (injectable via papermill / run_pipeline_step.py)
# Stations must have >= min_periods non-NaN years of data to be included
min_periods = 15
seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
layers = {'surface': 1, 'bottom': 2}
```

### Issue 3: Verifying Downstream Notebooks (08, 09, 10)

The downstream notebooks have not yet been tested with the new `subset_dir` parameter. They need to be run sequentially to verify correctness.

**Verification steps** (bypass DVC, run directly):

// turbo
```bash
# Step 1: Run decorrelation (Stage 2)
cd /home/reyha/SIS_Analysis_WSL
conda run -n sis_analysis papermill \
  notebooks/pipeline/08_Decorrelation_Analysis_v3.ipynb \
  notebooks/output/08_log.ipynb \
  2>&1 | tail -20
```

// turbo
```bash
# Step 2: Check for errors in the log notebook
cd /home/reyha/SIS_Analysis_WSL
conda run -n sis_analysis python3 -c "
import json
with open('notebooks/output/08_log.ipynb') as f:
    nb = json.load(f)
for i, cell in enumerate(nb['cells']):
    for o in cell.get('outputs', []):
        if o.get('output_type') == 'error':
            print(f'ERROR in cell {i}: {o[\"ename\"]}: {o[\"evalue\"]}')
            for line in o.get('traceback', [])[-5:]:
                print(line)
print('Done checking 08_log.')
"
```

// turbo
```bash
# Step 3: Verify output files exist
ls -la /home/reyha/SIS_Analysis_WSL/data/processed/seasonal/summer_bottom/stations_decorrelation_scale.csv
ls -la /home/reyha/SIS_Analysis_WSL/data/processed/dist_matrix_km.csv
```

// turbo
```bash
# Step 4: Run interpolation (Stage 3)
cd /home/reyha/SIS_Analysis_WSL
conda run -n sis_analysis papermill \
  notebooks/pipeline/09_Spatial_Interpolation_v2.ipynb \
  notebooks/output/09_log.ipynb \
  2>&1 | tail -20
```

// turbo
```bash
# Step 5: Check for errors
cd /home/reyha/SIS_Analysis_WSL
conda run -n sis_analysis python3 -c "
import json
with open('notebooks/output/09_log.ipynb') as f:
    nb = json.load(f)
for i, cell in enumerate(nb['cells']):
    for o in cell.get('outputs', []):
        if o.get('output_type') == 'error':
            print(f'ERROR in cell {i}: {o[\"ename\"]}: {o[\"evalue\"]}')
            for line in o.get('traceback', [])[-5:]:
                print(line)
print('Done checking 09_log.')
"
```

// turbo
```bash
# Step 6: Verify output
ls -la /home/reyha/SIS_Analysis_WSL/data/processed/seasonal/summer_bottom/interpolated_do_df.csv
```

// turbo
```bash
# Step 7: Run PCA (Stage 4)
cd /home/reyha/SIS_Analysis_WSL
conda run -n sis_analysis papermill \
  notebooks/pipeline/10_PCA_Analysis.ipynb \
  notebooks/output/10_log.ipynb \
  2>&1 | tail -20
```

// turbo
```bash
# Step 8: Check for errors
cd /home/reyha/SIS_Analysis_WSL
conda run -n sis_analysis python3 -c "
import json
with open('notebooks/output/10_log.ipynb') as f:
    nb = json.load(f)
for i, cell in enumerate(nb['cells']):
    for o in cell.get('outputs', []):
        if o.get('output_type') == 'error':
            print(f'ERROR in cell {i}: {o[\"ename\"]}: {o[\"evalue\"]}')
            for line in o.get('traceback', [])[-5:]:
                print(line)
print('Done checking 10_log.')
"
```

// turbo
```bash
# Step 9: Verify PCA outputs
ls -la /home/reyha/SIS_Analysis_WSL/data/processed/seasonal/summer_bottom/pca_*.csv
```

### Issue 4: Notebook Error Diagnosis Protocol

If any notebook fails, follow this protocol:

1. **Read the error** from the log notebook check script above.
2. **Identify the failing cell number** from the error output.
3. **Read the source notebook** to find the cell content:
   ```bash
   python3 -c "
   import json
   with open('notebooks/pipeline/XX_NOTEBOOK.ipynb') as f:
       nb = json.load(f)
   cell = nb['cells'][CELL_NUMBER]
   print(''.join(cell['source']))
   "
   ```
4. **Generate a fix** code snippet following the `/handle_jupyter_notebook_modification` workflow — do NOT edit .ipynb files directly.
5. **Present the fix** to the user for manual insertion.
6. **Re-run** the failed notebook using the papermill commands above.

## Regression Check

After all stages run successfully, compare the new `summer_bottom` subset outputs against the legacy flat files to ensure consistency:

// turbo
```bash
cd /home/reyha/SIS_Analysis_WSL
conda run -n sis_analysis python3 -c "
import pandas as pd

# Compare yearly DO
old = pd.read_csv('data/processed/yearly_do_df.csv', index_col=0)
new = pd.read_csv('data/processed/seasonal/summer_bottom/yearly_do_df.csv', index_col=0)
old.index = old.index.astype(str).str.zfill(8)
new.index = new.index.astype(str).str.zfill(8)
old.columns = old.columns.astype(int)
new.columns = new.columns.astype(int)
print(f'Old shape: {old.shape}, New shape: {new.shape}')
print(f'Shapes match: {old.shape == new.shape}')
if old.shape == new.shape:
    diff = (old - new).abs().max().max()
    print(f'Max absolute difference: {diff}')
else:
    common_idx = old.index.intersection(new.index)
    common_col = old.columns.intersection(new.columns)
    print(f'Common stations: {len(common_idx)}, Common years: {len(common_col)}')
"
```

## Completion Criteria

- [ ] All 8 `yearly_do_df.csv` files exist under `data/processed/seasonal/`
- [ ] `08_Decorrelation_Analysis_v3.ipynb` runs without errors and produces `stations_decorrelation_scale.csv` in `seasonal/summer_bottom/`
- [ ] `09_Spatial_Interpolation_v2.ipynb` runs without errors and produces `interpolated_do_df.csv` in `seasonal/summer_bottom/`
- [ ] `10_PCA_Analysis.ipynb` runs without errors and produces `pca_scores.csv`, `pca_loadings.csv`, `pca_variance.csv` in `seasonal/summer_bottom/`
- [ ] DVC symlink issue is resolved (or documented as a known limitation)
- [ ] Regression check passes (summer_bottom outputs match legacy flat files)

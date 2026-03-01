# Diffusion Equation Interpolation Guide

This document details the mathematical formulation and Python implementation of the physics-based spatial interpolation method using a steady-state diffusion equation, as extracted from `notebooks/20_diffusion_eq_interp.ipynb`.

## 1. Mathematical Formulation

The method assumes the property $C$ (e.g., Dissolved Oxygen concentration) is governed by 2D steady-state Laplacian diffusion:
$$ \nabla^2 C = \frac{\partial^2 C}{\partial x^2} + \frac{\partial^2 C}{\partial y^2} = 0 $$

### Boundary Conditions
1. **Dirichlet Boundary Conditions (Fixed points):** At grid cells where observations exist, the concentration is fixed to the observed value. $C(x_i, y_i) = C_{obs}$.
2. **Neumann Boundary Conditions (Zero-flux):** At the land-water interface, the flux across the boundary is zero. $ \frac{\partial C}{\partial n} = 0 $. In a discrete grid, this means a water cell does not exchange value with an adjacent land cell.

### Numerical Solver: Red-Black Successive Over-Relaxation (SOR)
We discretize the Laplacian using a 5-point stencil on a Cartesian grid. To solve the resulting sparse linear system efficiently in pure Python/NumPy, we use **Red-Black Successive Over-Relaxation (SOR)**. 
Grid cells are divided into a "checkerboard" pattern of Red and Black cells. The algorithm alternates between updating all Red cells (using neighboring Black cells) and all Black cells (using neighboring Red cells).
The update rule incorporating the relaxation factor $\omega$ ($1 < \omega < 2$) is:
$$ C_{new}^{(k+1)} = (1 - \omega) C^{(k)} + \omega \overline{C}_{neighbors}^{(k)} $$
where $\overline{C}_{neighbors}$ is the average of valid *water* neighbors (naturally enforcing the zero-flux Neumann boundary condition).

---

## 2. Python Implementation

The following function implements the Red-Black SOR solver. It requires `numpy` as `np`, `scipy.ndimage` as `ndimage`, and `logging` for output. Note that `grid_x` and `grid_y` (the 2D meshgrid arrays matching `water_mask`) should be accessible in the scope when calculating distance to snap stations to the grid. In this version, those variables have been added to the function signature explicitly for modular use.

```python
import numpy as np
import scipy.ndimage as ndimage
import logging

def run_diffusion_interpolation(year_data, station_locs_gdf, grid_x_1d, grid_y_1d, water_mask, grid_x, grid_y, max_iters=2000, tol=1e-4, omega=1.7):
    """
    Runs Red-Black SOR to solve the diffusion equation on the grid.
    
    Args:
        year_data: DataFrame containing 'Station_ID' and 'DO_mgL' for the target year.
        station_locs_gdf: GeoDataFrame mapping 'Station_ID' to shapely Point geometries (in matching CRS).
        grid_x_1d, grid_y_1d: 1D coordinate arrays for the grid axes.
        water_mask: 2D boolean numpy array where True represents a valid water cell.
        grid_x, grid_y: 2D meshgrid coordinate arrays corresponding to the grid.
        max_iters: Maximum solver iterations.
        tol: Convergence tolerance for maximum DO difference between iterations.
        omega: Relaxation factor for SOR (1 < omega < 2).
        
    Returns:
        Z: 2D numpy array of interpolated DO concentrations (with NaNs for land).
    """
    # Initialize the solution grid with NaNs (Land will remain NaN)
    Z = np.full(water_mask.shape, np.nan)
    
    # Provide an initial guess for water cells (e.g., mean observed DO)
    mean_val = year_data['DO_mgL'].mean()
    Z[water_mask] = mean_val
    
    # Create mask to track fixed observation cells
    fixed_mask = np.zeros_like(water_mask, dtype=bool)
    
    # Map observations to the nearest grid cell
    for idx, row in year_data.iterrows():
        station_id = row['Station_ID']
        if station_id in station_locs_gdf.index:
            pt = station_locs_gdf.loc[station_id].geometry
            # Find closest grid indices
            ix = np.argmin(np.abs(grid_x_1d - pt.x))
            iy = np.argmin(np.abs(grid_y_1d - pt.y))
            
            # Snap to grid if it's considered water
            if water_mask[iy, ix]:
                Z[iy, ix] = row['DO_mgL']
                fixed_mask[iy, ix] = True
            else:
                # If observation slightly in land due to grid resolution, find nearest water cell
                dist = (grid_x - pt.x)**2 + (grid_y - pt.y)**2
                dist[~water_mask] = np.inf
                nearest_water_flat_idx = np.argmin(dist)
                iy_nearest, ix_nearest = np.unravel_index(nearest_water_flat_idx, water_mask.shape)
                Z[iy_nearest, ix_nearest] = row['DO_mgL']
                fixed_mask[iy_nearest, ix_nearest] = True

    # Red-Black masks
    # Create checkerboard pattern
    i_indices, j_indices = np.indices(Z.shape)
    red_mask = (i_indices + j_indices) % 2 == 0
    black_mask = ~red_mask

    # Convolution kernel for 4-neighbors (Laplacian)
    kernel = np.array([[0, 1, 0], 
                       [1, 0, 1], 
                       [0, 1, 0]])
                       
    # Pre-calculate neighbor counts for water cells (handling Neumann BC automatically)
    # A cell near land will have < 4 valid neighbors to average over
    water_float = water_mask.astype(float)
    W = ndimage.convolve(water_float, kernel, mode='constant', cval=0.0)
    
    def update(Z_current, mask):
        # Only convolve over water cells (treat land and NaNs as 0 flux)
        Z_water = np.nan_to_num(Z_current, copy=True, nan=0.0) * water_mask
        
        # Sum of neighbors
        Z_sum = ndimage.convolve(Z_water, kernel, mode='constant', cval=0.0)
        
        # Average of neighbors (avoid div by zero, which shouldn't happen for water cells except 0-neighbor isolated grids)
        with np.errstate(divide='ignore', invalid='ignore'):
            Z_new = np.where(W > 0, Z_sum / W, Z_current)
            
        # Update only cells that are in the current color, are water, and are NOT fixed observations
        update_mask = mask & water_mask & (~fixed_mask)
        Z_current[update_mask] = (1 - omega) * Z_current[update_mask] + omega * Z_new[update_mask]
        return Z_current

    # SOR Iteration Loop
    for it in range(max_iters):
        Z_old = Z.copy()
        
        # Update Red cells, then Black cells
        Z = update(Z, red_mask)
        Z = update(Z, black_mask)
        
        # Check convergence
        diff = np.abs(Z[water_mask] - Z_old[water_mask])
        max_diff = np.nanmax(diff) if len(diff) > 0 else 0
        
        if (it + 1) % 200 == 0:
            logging.info(f"Iteration {it+1}: max diff = {max_diff:.6f}")
            
        if max_diff < tol:
            logging.info(f"Converged after {it+1} iterations! Max diff: {max_diff:.6f}")
            break
            
    if it == max_iters - 1:
        logging.warning("Reached max iterations without full convergence.")
        
    return Z
```

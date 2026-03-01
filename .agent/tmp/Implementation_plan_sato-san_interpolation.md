Create 20_diffusion_eq_interp.ipynb — Diffusion Equation Interpolation
Mirrors 

19_Kriging_test.ipynb
 but replaces Ordinary Kriging with iterative Laplacian diffusion (steady-state). Uses the same sea_area_mask_simplified.shp as the interpolation boundary. Method and terminology follow 

Sato_diffusion_interpolation.md
.

Proposed Changes
[NEW] 

20_diffusion_eq_interp.ipynb
Cell 1 — Markdown: Title & Introduction
Brief overview: physics-based spatial interpolation that simulates diffusion to steady state, respecting physical land boundaries.

Cell 2 — Markdown: Mathematical Logic
Explains the method using Sato-san's terminology:

Numerically solves the Laplace equation for steady-state concentration $\phi(x,y)$:
$$\frac{\partial^2}{\partial x^2}\phi(x,y) + \frac{\partial^2}{\partial y^2}\phi(x,y) = 0$$

Neumann boundary conditions: the concentration gradient at land and open-ocean boundaries is zero ($\nabla\phi \cdot \mathbf{n} = 0$), meaning no flux across physical boundaries.
Solved numerically using the SOR (Successive Over-Relaxation) method on a $1\text{ km} \times 1\text{ km}$ mesh.
Advantages: respects land topography (peninsulas, islands, reclaimed land).
Disadvantages: computationally expensive due to fine mesh.
Contrasts with purely mathematical methods (e.g., Spline, Linear) which interpolate flatly and cannot account for land boundaries.
Cell 3 — Code: Imports & Setup
Standard imports (pandas, numpy, matplotlib, geopandas, cartopy)
scipy.ndimage.convolve for diffusion solver
scipy.interpolate.griddata for linear interpolation comparison

ProjectPaths
 for path management
Cell 4 — Markdown: Section 1 — Load Data
Cell 5 — Code: Load Data
Same as notebook 19: Summer/bottom DO subset, distance matrix, decorrelation scales, station coordinates in UTM 53N.

Cell 6 — Markdown: Section 2 — Load Sea Area Mask & Build Grid
Cell 7 — Code: Sea Area Mask & Grid
Same as notebook 19: load sea_area_mask_simplified.shp, project to UTM 53N, build 1 km grid, filter to water-only points. Additionally build a 2D boolean water_mask array on the full grid for the diffusion solver.

Cell 8 — Markdown: Section 3 — Diffusion Equation Interpolation
Cell 9 — Code: Diffusion Interpolation (Single Year)
Select a representative year
Map station DO values onto the nearest 2D grid cells (fixed observation points)
Initialize unknown water cells with mean observed DO
Implement Neumann BCs: at each diffusion step, each water cell averages only its water neighbors (land cells excluded), enforcing zero-gradient at land boundaries
Apply SOR iterations: Z_new = Z + omega * (Z_avg - Z) where omega ≈ 1.5 is the relaxation factor
Reset observation cells to true values at each step
Converge when max(|Z_new - Z|) < threshold on water cells
Extract predicted values at the water grid points
Cell 10 — Markdown: Section 4 — Visualize Diffusion Results
Cell 11 — Code: Map of Interpolated DO Surface (Diffusion)
Same Cartopy layout as notebook 19: PlateCarree projection, land from boundary shapefile, scatter plot of predictions, stations overlay, colorbar.

Cell 12 — Markdown: Section 5 — Linear Interpolation Comparison
Explains that linear interpolation (a purely mathematical method) is applied on the same masked grid to visually demonstrate how it ignores physical land boundaries.

Cell 13 — Code: Linear Interpolation Map
Use scipy.interpolate.griddata(method='linear') to interpolate DO onto the same water-masked grid
Plot with the same Cartopy layout for side-by-side visual comparison with the diffusion result
Cell 14 — Markdown: Section 6 — LOOCV Validation
Cell 15 — Code: Leave-One-Out Cross-Validation
Hold out one station at a time, re-run the diffusion solver, predict held-out station value, collect errors. Process first 5 years.

Cell 16 — Markdown: Section 7 — LOOCV Results
Cell 17 — Code: LOOCV Metrics & Scatter Plot
MAE, RMSE, predicted-vs-true scatter plot (same layout as notebook 19).

Cell 18 — Markdown: Conclusions
Evaluate whether the computational expense of the Diffusion Equation method provides visibly superior results, especially around complex coastlines, compared to Linear Interpolation.

Verification Plan
Manual Verification (User)
Open notebooks/20_diffusion_eq_interp.ipynb and run all cells with sis_analysis
Confirm the SOR solver converges within a reasonable iteration count
Confirm the DO map shows smooth spatial gradients constrained to water areas
Visually compare the diffusion map vs. the linear interpolation map — diffusion should show better handling around islands/peninsulas
Compare LOOCV MAE/RMSE with kriging results from notebook 19
Based on the paper "Estimation of two dimensional water quality profile by means of the interpolation methods," here is a detailed description of the four interpolation methods examined, including their mathematical foundations and how they were performed in the study.

The authors utilized a "cross-validation" technique to optimize the parameters for each method. This involved removing one data point, estimating it using the remaining points, and repeating this for all points to minimize the average relative error.

### 1. Moving Average Method (WT)
This is a conventional, computationally simple method often applied to environmental data like air quality.

*   **Calculation Principle:**
    The concentration $c^*(x_s)$ at an arbitrary point $x_s$ is calculated as a weighted average of the measured values $c(x_i)$ at monitoring points $x_i$. The weight is determined by the distance $r_{is}$ between the estimation point and the monitoring point.
    
    The formula used is:
    $$c^*(x_s) = \frac{\sum_{i=1}^{n} (1/r_{is}^N) \cdot c(x_i)}{\sum_{i=1}^{n} (1/r_{is}^N)}$$
    
    Where:
    *   $N$ is a weighting parameter ($N > 0$).
    *   $r_{is}$ is the Euclidean distance between points.

*   **Performance:**
    The shape of the distribution changes significantly based on the value of $N$. If $N$ is large, the estimate is heavily influenced by the nearest neighbor; if small, it becomes a broad average. In this study, the optimal $N$ was determined effectively by finding the value that minimized prediction error. For example, in one Osaka Bay dataset, the optimum $N$ was found to be 4.65.

### 2. Tension Spline Method (SP)
This method fits a smooth surface to the data points, designed to avoid the unnatural oscillations often seen in standard polynomial interpolation.

*   **Calculation Principle:**
    The method seeks a surface $c^*(x)$ that passes through all observed data points ($c^*(x_i) = c(x_i)$) while minimizing a specific "energy" functional $J$ that represents the surface's roughness and tension:
    
    $$J(c^*) = \iint \{ (\Delta c^*)^2 + k^2 (\nabla c^*)^2 \} ds$$
    
    Where:
    *   $\Delta$ is the Laplacian operator (curvature).
    *   $\nabla$ is the gradient operator (slope).
    *   $k$ is the "spline coefficient" or tension parameter.

    Mathematically, this results in solving the Euler equation: $\Delta^2 c^* - k^2 \Delta c^* = 0$. The solution is constructed by superimposing fundamental solutions involving the modified Bessel function of the second kind, $K_0(kr)$.

*   **Performance:**
    The parameter $k$ controls the smoothness. A small $k$ produces a very smooth, plate-like surface, while a large $k$ creates sharp peaks around data points. The authors determined the optimal $k$ via cross-validation to balance smoothness and accuracy.

### 3. Kriging Method (KG)
This is a statistical method (specifically Universal Kriging) that accounts for the spatial correlation between data points. It is theoretically rigorous but computationally complex.

*   **Calculation Principle:**
    The estimate $c^*(x_s)$ is a linear combination of observed values: $c^*(x_s) = \sum \lambda_i c(x_i)$. The weights $\lambda_i$ are calculated to satisfy two statistical conditions:
    1.  **Unbiasedness:** The expected error is zero ($E[c^* - c] = 0$).
    2.  **Minimum Variance:** The variance of the estimation error is minimized.

    The method assumes the water quality field consists of a "trend" (drift) and a random error. The spatial correlation of the random error is described by a **Generalized Covariance Function** $G(h)$, where $h$ is the distance between points. The study used a function of the form:
    $$G(h) = a_0 \delta(h) - a_1 |h|$$
    Where $\delta(h)$ is a function that is 1 at distance zero and 0 otherwise (representing the "nugget" effect or noise), and $|h|$ represents the linear dependence on distance.

*   **Performance:**
    The coefficients $a_0$ and $a_1$ were estimated by minimizing the "leave-one-out" error (cross-validation). This method provided the best overall fit in the study's comparisons.

### 4. Convective Diffusion Method (CD)
This is the **new method proposed by the authors**. It attempts to incorporate physical causality—specifically how water flows and mixes—into the interpolation process.

*   **Calculation Principle:**
    Instead of just fitting points mathematically, this method finds a surface that minimizes the residual of the **steady-state convective diffusion equation** (a physical law governing pollutant transport).
    
    The physical equation governing the concentration $c$ is:
    $$M \frac{\partial c}{\partial x} + N \frac{\partial c}{\partial y} = D_x \frac{\partial^2 c}{\partial x^2} + D_y \frac{\partial^2 c}{\partial y^2} - bc$$
    
    Where:
    *   $M, N$: Flow flux in $x$ and $y$ directions (current velocity).
    *   $D_x, D_y$: Diffusion coefficients.
    *   $b$: Reaction/decay rate (often assumed negligible for conservative substances).

    The method minimizes a functional $J(c^*)$ that includes the square of the error in this physical equation, weighted by a reliability factor, along with terms ensuring the surface matches the observed data and boundary conditions.

*   **Performance:**
    *   **Discretization:** The area was divided into a grid (e.g., 1.5 km mesh for Osaka Bay). The differential equations were converted into finite difference equations. At grid points near monitoring stations, the equation was adjusted to force the surface to pass through the observed data.
    *   **Inputs:** This method requires prior knowledge of the flow field (currents). For Osaka Bay, a steady circulation pattern (clockwise flow of 5–10 cm/s) was assumed based on prior knowledge.
    *   **Optimization:** The diffusion coefficient $D$ was treated as a tuning parameter and optimized via cross-validation, similar to the tension parameter in the Spline method.
    *   **Results:** The CD method performed comparably to Kriging and was superior in simulated environments where strong currents existed, as it could predict "upstream" and "downstream" effects that purely mathematical methods missed.
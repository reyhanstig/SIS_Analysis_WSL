Based on Sato-san's report, here is a summary of the spatial interpolation methods used for creating water quality concentration maps. The text primarily details a physics-based diffusion method, while briefly contrasting it with a mathematical spline method used in the past.

### Primary Method: Diffusion Equation Interpolation

This method interpolates missing data between actual measurement points by simulating physical diffusion until it reaches a steady state.

* **Core Mechanism:** It numerically solves the Laplace equation to achieve a steady-state solution where the calculated values no longer change:

$$\frac{\partial^2}{\partial x^2}\phi(x,y) + \frac{\partial^2}{\partial y^2}\phi(x,y) = 0$$


* **Boundary Conditions:** It applies Neumann boundary conditions, meaning the concentration difference (gradient) at the boundaries with land or the open ocean is set to zero.
* **Numerical Method:** The equation is solved using the **SOR (Successive Over-Relaxation)** method.
* **Advantages:** Unlike simple mathematical smoothing, this method respects physical boundaries. It correctly accounts for land topography, such as peninsulas, islands, and reclaimed land, ensuring the interpolation reflects actual physical diffusion around these obstacles.
* **Disadvantages:** It is highly computationally expensive. Because it relies on fine mesh calculations (e.g., $0.5\text{ km} \times 0.5\text{ km}$ for Tokyo/Ise Bays and $1\text{ km} \times 1\text{ km}$ for the Seto Inland Sea), it requires significant processing time.

---

### Previous Alternative: Spline Function Interpolation

The document also notes that an older report used a different method based on spline functions.

* **Mechanism:** A purely mathematical approach designed to minimize the curvature of the contour lines.
* **Advantages:** It does not require heavy mesh calculations, making it computationally lightweight and easy to run even on lower-spec computers.
* **Disadvantages:** It interpolates flatly across a 2D plane and **cannot** account for land topography or water/land boundaries, making it less physically realistic for complex coastlines.
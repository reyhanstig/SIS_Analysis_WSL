# Apply SIS Mapping Standard

**Description:** 
Whenever generating or modifying geospatial visualizations, plots, or maps for the Seto Inland Sea (SIS) analysis pipeline, you must strictly adhere to the global mapping standards defined for the project, **unless the user explicitly requests to override or not use this standard** (e.g., if they request specific custom layouts, compact sizing, or custom styling parameters).

## Instructions
When creating or editing plotting scripts (matplotlib, cartopy, etc.), follow these rules:

1. **Always use the centralized project style:**
   Include the following line after importing matplotlib to apply the global configuration:
   ```python
   import matplotlib.pyplot as plt
   plt.style.use('../project_style.mplstyle') # Adjust relative path based on script location
   ```

2. **Follow Global Font Size Settings:**
   Do not hardcode or override font sizes with smaller custom values for compact layouts unless absolutely necessary and approved by the user. The standard sizes enforced by the style are:
   - **Title**: Bold, Size 20
   - **Axis Labels**: Size 18
   - **Tick Labels**: Size 16
   - **Legend**: Size 12
   - **Global Base Font**: Size 16 (controls scatter labels and annotations)

3. **Reference the Main Document:**
   For additional mapping rules—such as setting up multi-subplot figures, custom coastal boundaries, Z-order management, and dynamic gridline/extent configurations—you must read the full `reports/SIS_mapping_standard.md` document before finalizing any mapping scripts.

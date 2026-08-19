import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()

text = """# Comparison of Map Scaling Logic
This notebook demonstrates the difference between the **Old Map Extent Logic** (a flat geographic 0.2 degree buffer) and the **New Map Extent Logic** (a proportional 10% buffer with dynamic figure aspect ratios).

Notice how the old logic creates a massive ocean padding around narrow areas like Tokyo Bay, whereas the new logic keeps the box tightly fitted to the data bounds!"""
nb.cells.append(nbf.v4.new_markdown_cell(text))

regions = ['tokyo_bay', 'ise_bay', 'seto_inland_sea']

for region in regions:
    region_title = region.replace('_', ' ').title()
    cell_md = f"## {region_title}\n\n"
    
    cell_md += f"### Old Logic (Fixed 0.2 Degree Buffer)\n"
    cell_md += f"![{region_title} Old](../../figures/test/old_logic/spatial_corr_{region}.png)\n\n"
    
    cell_md += f"### New Logic (10% Proportional Buffer)\n"
    cell_md += f"![{region_title} New](../../figures/test/new_logic/spatial_corr_{region}.png)\n\n"
    
    nb.cells.append(nbf.v4.new_markdown_cell(cell_md))
    
out_path = Path('/home/reyha/SIS_Analysis_WSL/step0_sandbox/compare_map_extents.ipynb')
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, 'w') as f:
    nbf.write(nb, f)
print("Notebook created.")

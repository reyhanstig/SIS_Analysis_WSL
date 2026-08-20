import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()

# Markdown cell summarizing findings
text_cells = []
text_cells.append(nbf.v4.new_markdown_cell("""# Summary: Mapping Buffer Logic Comparison
This notebook compares the mapping outputs of the previous **fixed padding logic** vs. the new **proportional padding logic**.

## Key Findings:
- **Seto Inland Sea (Global extent):** By explicitly excluding the global "Seto Inland Sea" map from the proportional buffer, we maintained the exact aspect ratio and fixed buffer defined in the `SIS_mapping_standard.md`, preserving the standardized overview maps.
- **Smaller/Individual Bays:** The new proportional buffer (10-11% buffer using dynamic extent logic) correctly applies padding dynamically depending on each bay's actual lat/lon span. This solves the previous issue where smaller bays appeared heavily zoomed out with excessive empty space around them.
- **Aspect Ratio:** The proportional buffer combined with dynamic figure sizing keeps the Cartesian aspect ratio correct based on the central latitude, avoiding distorted visual stretches.

Below are visual comparisons side-by-side for different pipeline plotting stages.
"""))

# Code cell to display side-by-side images
code_template = """from IPython.display import HTML, display

def display_side_by_side(img1, img2, title1="Old Logic (Fixed Buffer)", title2="New Logic (Proportional Buffer)"):
    html_code = f'''
    <div style="display: flex; flex-direction: row;">
        <div style="flex: 50%; padding: 5px; text-align: center;">
            <h3>{title1}</h3>
            <img src="{img1}" style="width:100%">
        </div>
        <div style="flex: 50%; padding: 5px; text-align: center;">
            <h3>{title2}</h3>
            <img src="{img2}" style="width:100%">
        </div>
    </div>
    '''
    display(HTML(html_code))
"""

text_cells.append(nbf.v4.new_code_cell(code_template))

# Comparisons
comparisons = [
    ("Seto Inland Sea Trend Map (Global Extent fallback)", "trend_seto_inland_sea.png"),
    ("Tokyo Bay PCA Mapping", "pca_tokyo_bay.png"),
    ("Ise Bay Decorrelation Scale", "decorrelation_ise_bay.png"),
    ("Tokyo Bay Spatial Correlation Map", "spatial_corr_tokyo_bay.png")
]

for title, filename in comparisons:
    text_cells.append(nbf.v4.new_markdown_cell(f"### {title}"))
    code = f"display_side_by_side('../figures/test/old_logic/{filename}', '../figures/test/new_logic/{filename}')"
    text_cells.append(nbf.v4.new_code_cell(code))

nb['cells'] = text_cells

out_path = Path('step0_sandbox/68d_summary_buffer_comparison.ipynb')
nbf.write(nb, str(out_path))
print(f"Generated notebook at {out_path}")

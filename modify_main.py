import sys

path = 'step5_environmental_factor_correlation_analysis/main.py'
with open(path, 'r') as f:
    lines = f.readlines()

new_lines = []
in_loop = False
for i, line in enumerate(lines):
    if "season = params.get('season', 'Summer')" in line:
        new_lines.append("    seasons_str = params.get('seasons', 'Spring, Summer, Autumn, Winter')\n")
        new_lines.append("    layers_str = params.get('layers', 'surface, bottom')\n")
        new_lines.append("    seasons = [s.strip() for s in seasons_str.split(',')]\n")
        new_lines.append("    layers = [l.strip() for l in layers_str.split(',')]\n")
        continue
    if "layer = params.get('layer', 'bottom')" in line:
        continue
    if "subset_dir = ProjectPaths.get_subset_dir(season, layer)" in line:
        # Skip for now, we will add it inside the loop
        continue
    
    if "code = run_script(step_dir, env, 'process21_decorrelation_drivers.py'" in line:
        in_loop = True
        new_lines.append("    for season in seasons:\n")
        new_lines.append("        for layer in layers:\n")
        new_lines.append("            subset_dir = ProjectPaths.get_subset_dir(season, layer)\n")
        
    if in_loop and line.strip() and not line.startswith("    logging.info(\"All orchestrations"):
        new_lines.append("        " + line)
    else:
        new_lines.append(line)
        if "logging.info(\"All orchestrations" in line:
            in_loop = False

with open(path, 'w') as f:
    f.writelines(new_lines)
print("Done")

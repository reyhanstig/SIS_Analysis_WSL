class MappingConfig:
    """Standardized configuration for mapping figures in the SIS Analysis Pipeline."""
    
    # --- Z-Orders ---
    ZORDER_OCEAN = 0               # Handled largely via set_facecolor on axis
    ZORDER_CARTOPY_LAND = 0.5      # Cartopy low-res land feature
    ZORDER_CARTOPY_COASTLINE = 0.6 # Cartopy low-res coastline
    ZORDER_LAND = 4                # Setonaikai high-res land boundary shapefile
    ZORDER_GRIDLINES = 10          # Cartopy gridlines (now on top of everything)
    ZORDER_PREDICTED = 3           # Interpolated grids, contours, or scatters
    ZORDER_OBSERVATIONS = 5        # Actual observation scatter points
    
    # --- Boundary Files ---
    LAND_BOUNDARY_FILENAME = "Setonaikai_boundary_2.shp"
    
    @staticmethod
    def apply_global_plot_styles():
        """Applies global matplotlib parameter updates for consistent styling."""
        import matplotlib.pyplot as plt
        plt.rcParams.update({
            'font.size': 12,              # Minimal base font size
            'axes.titlesize': 14,         # Plot title font size
            'axes.labelsize': 12,         # X/Y axis label font size
            'xtick.labelsize': 10,        # X axis tick label size
            'ytick.labelsize': 10,        # Y axis tick label size
            'legend.fontsize': 10,        # Legend font size
            'axes.titleweight': 'bold',   # Bold plot titles by default
            'figure.titlesize': 16,       # Super title font size
            'figure.titleweight': 'bold'  # Bold super titles
        })

    BOUNDARY_FILES = {
        'Seto Inland Sea': 'Setonaikai_boundary_2.shp',
        'Tokyo Bay': 'Tokyobay_boundary.shp',
        'Ise Bay': 'Isebay_boundary.shp',
        'Japan': '../Whole nation administrative boundary/N03-20240101_prefecture(simplified0.01).shp'
    }
    
    @staticmethod
    def get_boundary_file(target_region):
        """Returns the appropriate boundary filename for the given region."""
        return MappingConfig.BOUNDARY_FILES.get(target_region, MappingConfig.LAND_BOUNDARY_FILENAME)
    
    @staticmethod
    def load_target_region():
        """Loads the target region from params.yaml."""
        import yaml
        from utils.paths import ProjectPaths
        try:
            params_path = ProjectPaths.PROJECT_ROOT / "params.yaml"
            if params_path.exists():
                with open(params_path, "r") as f:
                    params = yaml.safe_load(f)
                    return params.get('mapping', {}).get('target_region', 'Seto Inland Sea')
        except Exception:
            pass
        return 'Seto Inland Sea'

    # --- Land / Ocean Styling ---
    COLOR_OCEAN = 'lightblue'
    COLOR_LAND = 'lightgray'
    COLOR_LAND_EDGE = 'black'
    LINEWIDTH_LAND = 0.5
    
    # --- Gridline Styling ---
    GRID_COLOR = 'gray'
    GRID_ALPHA = 0.5
    GRID_LINESTYLE = '--'
    GRID_LINEWIDTH = 0.5
    
    @staticmethod
    def apply_gridlines(ax):
        """Helper method to draw gridlines with correct z-orders."""
        gl = ax.gridlines(draw_labels=True, linestyle=MappingConfig.GRID_LINESTYLE,
                          color=MappingConfig.GRID_COLOR, alpha=MappingConfig.GRID_ALPHA,
                          linewidth=MappingConfig.GRID_LINEWIDTH, zorder=MappingConfig.ZORDER_GRIDLINES)
        
        # CRITICAL: The Gridliner object itself must have its zorder set,
        # otherwise its draw() method is called too early (default zorder=2)
        gl.set_zorder(MappingConfig.ZORDER_GRIDLINES)
        
        # In cartopy >= 0.20, xline_artists is a list of lines
        if hasattr(gl, 'xline_artists'):
            for line in gl.xline_artists:
                line.set_zorder(MappingConfig.ZORDER_GRIDLINES)
        if hasattr(gl, 'yline_artists'):
            for line in gl.yline_artists:
                line.set_zorder(MappingConfig.ZORDER_GRIDLINES)
                
        gl.top_labels = False
        gl.right_labels = False
        return gl
    
    # --- Variable-Specific Mappings ---
    # Defines the colormaps, bounds, and labels dynamically based on the dataset variable
    VARIABLE_SETTINGS = {
        'do_': {
            'cmap': 'jet_r',
            'vmin': 0.0,
            'vmax': 12.0,
            'label': 'DO Concentration (mg/L)',
            'extend': 'both',
            'tick_step': 2.0
        },
        'temperature': {
            'cmap': 'RdYlBu_r',
            'vmin': 0.0,
            'vmax': 39.0,
            'label': 'Air Temperature (\u00b0C)',
            'extend': 'neither',
            'tick_step': 5.0
        },
        'temp': { # Alias for Air Temperature
            'cmap': 'RdYlBu_r',
            'vmin': 0.0,
            'vmax': 39.0,
            'label': 'Air Temperature (\u00b0C)',
            'extend': 'neither',
            'tick_step': 5.0
        },
        'water_temperature': {
            'cmap': 'RdYlBu_r',
            'vmin': 10.0,
            'vmax': 30.0,
            'label': 'Water Temperature (\u00b0C)',
            'extend': 'neither',
            'tick_step': 5.0
        },
        'wtemp': { # Alias for Water Temperature
            'cmap': 'RdYlBu_r',
            'vmin': 10.0,
            'vmax': 30.0,
            'label': 'Water Temperature (\u00b0C)',
            'extend': 'neither',
            'tick_step': 5.0
        },
        'salinity': {
            'cmap': 'viridis',
            'vmin': 31.0,
            'vmax': 35.0,
            'label': 'Salinity (PSU)',
            'extend': 'min',
            'tick_step': 1.0
        },
        'salt': { # Alias for Salinity
            'cmap': 'viridis',
            'vmin': 31.0,
            'vmax': 35.0,
            'label': 'Salinity (PSU)',
            'extend': 'min',
            'tick_step': 1.0
        }
    }
    
    @staticmethod
    def get_var_settings(variable_name):
        """
        Retrieves styling dictionary for a given variable. 
        Falls back to a default style if the variable is not explicitly defined.
        """
        return MappingConfig.VARIABLE_SETTINGS.get(variable_name, {
            'cmap': 'RdYlBu',
            'vmin': 0.0,
            'vmax': 10.0,
            'label': f'{variable_name} Value',
            'extend': 'both',
            'tick_step': 2.0
        })
        
    @staticmethod
    def format_colorbar_ticks(cbar, variable_name):
        import numpy as np
        var_settings = MappingConfig.get_var_settings(variable_name)
        vmin = var_settings['vmin']
        vmax = var_settings['vmax']
        tick_step = var_settings.get('tick_step', 1.0)
        
        # Calculate ticks from vmin to vmax with tick_step
        # Ensuring first and last are definitely vmin and vmax
        ticks = np.arange(vmin, vmax, tick_step)
        
        # Make sure vmax is included as the last tick
        if len(ticks) == 0 or ticks[-1] != vmax:
            ticks = np.append(ticks, vmax)
            
        cbar.set_ticks(ticks)
        
        # Avoid decimal formatting if the tick values themselves are essentially integers
        # E.g., for non-decimal increment requirement
        tick_labels = []
        for t in ticks:
            if float(t).is_integer():
                tick_labels.append(f"{int(t)}")
            else:
                tick_labels.append(f"{t}")
        cbar.set_ticklabels(tick_labels)

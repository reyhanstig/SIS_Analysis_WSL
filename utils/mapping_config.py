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
    def get_dynamic_extent(target_region, plot_data=None):
        """
        Returns the [xmin, xmax, ymin, ymax] extent for mapping.
        For Seto Inland Sea, it loads the fixed computational water polygon bounds.
        For others, it dynamically calculates a proportional 11% buffer around the data bounds.
        """
        import geopandas as gpd
        from utils.paths import ProjectPaths
        if target_region == 'Seto Inland Sea':
            water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_sis_simplified.shp"
            if water_boundary_path.exists():
                sis_water_boundary = gpd.read_file(water_boundary_path)
                if sis_water_boundary.crs != "EPSG:4326":
                    sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
                bounds = sis_water_boundary.total_bounds
                return [bounds[0] + 0.1, bounds[2] + 0.1, bounds[1] - 0, bounds[3] + 0.2]
        
        if plot_data is not None:
            if hasattr(plot_data, 'total_bounds'):
                bounds = plot_data.total_bounds
                minx, maxx, miny, maxy = bounds[0], bounds[2], bounds[1], bounds[3]
            else:
                # Handle standard pandas DataFrame
                if 'longitude' in plot_data.columns and 'latitude' in plot_data.columns:
                    minx, maxx = plot_data['longitude'].min(), plot_data['longitude'].max()
                    miny, maxy = plot_data['latitude'].min(), plot_data['latitude'].max()
                elif 'lon' in plot_data.columns and 'lat' in plot_data.columns:
                    minx, maxx = plot_data['lon'].min(), plot_data['lon'].max()
                    miny, maxy = plot_data['lat'].min(), plot_data['lat'].max()
                else:
                    raise ValueError("plot_data must have 'longitude'/'latitude' or 'lon'/'lat' columns")
                
            x_range = maxx - minx
            y_range = maxy - miny
            
            x_buffer = max(x_range * 0.11, 0.06)
            y_buffer = max(y_range * 0.11, 0.06)
            
            return [minx - x_buffer, maxx + x_buffer, miny - y_buffer, maxy + y_buffer]
            
        return [130.8, 135.3, 33.0, 34.9] # Fallback for SIS

    @staticmethod
    def get_dynamic_figsize(extent, base_width=8, is_subplot=False, n_rows=1, n_cols=1, max_height=8.0):
        """
        Calculates the appropriate figsize to prevent Cartopy squishing due to aspect ratio.
        Includes a max_height cap to ensure font sizes do not appear diminished on tall/square regions (like Tokyo Bay) when viewed on screen.
        """
        aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])
        if is_subplot:
            width_per_subplot = base_width / n_cols
            height_per_subplot = (width_per_subplot * aspect_ratio) + 0.3
            fig_height = (height_per_subplot * n_rows) + 1.5 
            if fig_height > max_height:
                scale = max_height / fig_height
                return (base_width * scale, fig_height * scale)
            return (base_width, fig_height)
        else:
            fig_height = base_width * aspect_ratio
            if fig_height > max_height:
                scale = max_height / fig_height
                return (base_width * scale, fig_height * scale)
            return (base_width, fig_height)
    
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
        },
        'salt2': { # Alias for Salinity
            'cmap': 'viridis',
            'vmin': 31.0,
            'vmax': 35.0,
            'label': 'Salinity (PSU)',
            'extend': 'min',
            'tick_step': 1.0
        },
        'doc': {
            'cmap': 'YlGnBu',
            'vmin': 0.0,
            'vmax': 5.0,
            'label': 'DOC (mg/L)',
            'extend': 'max',
            'tick_step': 1.0
        },
        'doc2': {
            'cmap': 'YlGnBu',
            'vmin': 0.0,
            'vmax': 5.0,
            'label': 'DOC (mg/L)',
            'extend': 'max',
            'tick_step': 1.0
        },
        'density': {
            'cmap': 'cividis',
            'vmin': 15.0,
            'vmax': 27.0,
            'label': 'Density (kg/m\u00b3)',
            'extend': 'both',
            'tick_step': 3.0
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

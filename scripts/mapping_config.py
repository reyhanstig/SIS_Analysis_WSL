class MappingConfig:
    """Standardized configuration for mapping figures in the SIS Analysis Pipeline."""
    
    # --- Z-Orders ---
    ZORDER_OCEAN = 0         # Handled largely via set_facecolor on axis
    ZORDER_LAND = 1          # Setonaikai land boundary
    ZORDER_GRIDLINES = 2     # Cartopy gridlines
    ZORDER_PREDICTED = 3     # Interpolated grids, contours, or scatters
    ZORDER_OBSERVATIONS = 5  # Actual observation scatter points
    
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
    
    # --- Variable-Specific Mappings ---
    # Defines the colormaps, bounds, and labels dynamically based on the dataset variable
    VARIABLE_SETTINGS = {
        'do_': {
            'cmap': 'jet_r',
            'vmin': 0.0,
            'vmax': 12.0,
            'label': 'DO Concentration (mg/L)'
        },
        'temperature': {
            'cmap': 'coolwarm',
            'vmin': 10.0,
            'vmax': 30.0,
            'label': 'Temperature (\u00b0C)'
        },
        'salinity': {
            'cmap': 'viridis',
            'vmin': 25.0,
            'vmax': 35.0,
            'label': 'Salinity (PSU)'
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
            'label': f'{variable_name} Value'
        })

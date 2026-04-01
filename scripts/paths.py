from pathlib import Path
import os
import sys

class ProjectPaths:
    """
    Centralized path management for the project.

    INSTRUCTIONS FOR WRITING PATHS:
    ------------------------------
    Always use this class to handle file paths instead of hardcoding strings.
    This ensures compatibility across Windows and WSL/Linux.
    
    This configuration integrates with WSL/Windows symlinks at the project root:
    - data -> /mnt/c/Users/reyha/Documents/SIS_Analysis_Windows/data
    - figures -> /mnt/c/Users/reyha/Documents/SIS_Analysis_Windows/figures

    Usage Examples:
    1. Import the class:
       from scripts.paths import ProjectPaths

    2. Construct new paths using the '/' operator (pathlib standard):
       new_file_path = ProjectPaths.PROCESSED_DATA_DIR / "my_analysis_result.csv"

    3. Access specific defined files:
       data = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    """
    # Get the project root directory (parent of the scripts directory)
    # Assuming this script is in SIS_Analysis/scripts/
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    # Data Directories (Symlink in Project Root)
    DATA_DIR = PROJECT_ROOT / "data"
    
    # Check if data directory is a valid symlink or directory
    if not DATA_DIR.exists():
        print(f"Warning: Data directory {DATA_DIR} not found. Using local fallback/placeholders.")

    RAW_DATA_DIR = DATA_DIR / "raw" / "environmental_data"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    BOUNDARIES_DIR = DATA_DIR / "boundaries"
    
    # Bathymetry Raw Paths
    BATHYMETRY_GEBCO_DIR = DATA_DIR / "raw" / "GEBCO_10_Mar_2026_d2286085bd59"
    BATHYMETRY_JODC_DIR = DATA_DIR / "raw" / "JODC_mesh500_SIS"
    
    
    # Processed Files (Pipeline Artifacts)
    MERGED_DATA_FILE = PROCESSED_DATA_DIR / "merged_gdf.feather"
    
    # Decorrelation Analysis Outputs
    YEARLY_DO_FILE = PROCESSED_DATA_DIR / "yearly_do_df.csv"
    DIST_MATRIX_FILE = PROCESSED_DATA_DIR / "dist_matrix_km.csv"
    DECORRELATION_SCALE_FILE = PROCESSED_DATA_DIR / "stations_decorrelation_scale.csv"
    
    # Interpolation Outputs
    INTERPOLATED_DO_FILE = PROCESSED_DATA_DIR / "interpolated_do_df.csv"
    
    # PCA Analysis Outputs
    PCA_SCORES_FILE = PROCESSED_DATA_DIR / "pca_scores.csv"
    PCA_LOADINGS_FILE = PROCESSED_DATA_DIR / "pca_loadings.csv"
    PCA_VARIANCE_FILE = PROCESSED_DATA_DIR / "pca_variance.csv"
    PCA_ENV_CORR_PC1_FILE = PROCESSED_DATA_DIR / "pca_env_corr_pc1.csv"
    PCA_ENV_CORR_PC2_FILE = PROCESSED_DATA_DIR / "pca_env_corr_pc2.csv"

    # ---------------------------------------------------------------------------
    # Seasonal Subsets
    # Directory structure:  data/processed/seasonal/{season_lower}_{layer_lower}/
    # Valid seasons : Spring, Summer, Autumn, Winter
    # Valid layers  : surface (saisuipoin=1), bottom (saisuipoin=2)
    # ---------------------------------------------------------------------------
    SEASONAL_DATA_DIR = PROCESSED_DATA_DIR / "seasonal"
    LAYER_CODES = {"surface": 1, "bottom": 2}  # mapping used when filtering

    # Reference Files
    SOURCES_DIR = PROJECT_ROOT / "sources"
    
    # Corrected path for water manual based on data structure
    # Previously in sources/, now aligned with data structure
    WATER_MANUAL_PATH = DATA_DIR / "raw" / "environmental_manual" / "water_manual.xls"

    # Output Directories
    REPORTS_DIR = PROJECT_ROOT / "reports"
    
    # Figures Directory (Symlink in Project Root)
    FIGURES_DIR = PROJECT_ROOT / "figures"

    # ------------------------------------------------------------------
    # Seasonal subset helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_subset_dir(cls, season: str, layer: str) -> Path:
        """Return the processed subdirectory for a given season / layer combination.

        Args:
            season: One of 'Spring', 'Summer', 'Autumn', 'Winter'
                    (case-insensitive).
            layer:  One of 'surface' or 'bottom' (case-insensitive).

        Returns:
            ``data/processed/seasonal/{season_lower}_{layer_lower}/``

        Example::

            ProjectPaths.get_subset_dir('Summer', 'bottom')
            # → data/processed/seasonal/summer_bottom/
        """
        key = f"{season.lower()}_{layer.lower()}"
        return cls.SEASONAL_DATA_DIR / key

    @classmethod
    def ensure_subset_dir(cls, season: str, layer: str) -> Path:
        """Create (if needed) and return the subset directory."""
        d = cls.get_subset_dir(season, layer)
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def ensure_directories(cls):
        """Ensure that critical output directories exist."""
        # Only attempt to create if not a broken symlink
        try:
            if not cls.PROCESSED_DATA_DIR.exists():
                cls.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
            
            if not cls.FIGURES_DIR.exists():
                # Check if it's a symlink first
                if cls.FIGURES_DIR.is_symlink():
                    print(f"Warning: Figures directory is a broken symlink: {cls.FIGURES_DIR}")
                else:
                    cls.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not ensure directories: {e}")

    # ---------------------------------------------------------------------------
    # Seasonal Plots Output Directories
    # ---------------------------------------------------------------------------
    SEASONAL_PLOTS_DIR = FIGURES_DIR / "seasonal_plots"

    @classmethod
    def verify_symlinks(cls):
        """Check status of project symlinks."""
        links = {
            "data": cls.DATA_DIR,
            "figures": cls.FIGURES_DIR
        }
        
        status = {}
        for name, path in links.items():
            is_symlink = path.is_symlink()
            exists = path.exists()
            target = path.resolve() if exists else "Broken"
            status[name] = {
                "is_symlink": is_symlink,
                "exists": exists,
                "target": str(target)
            }
        return status

    @classmethod
    def get_seasonal_plots_dir(cls, parameter: str, plot_type: str) -> Path:
        """
        Get the directory for a specific type of seasonal plot.
        Creates the directory if it doesn't exist.
        
        Args:
            parameter: The parameter name (e.g., 'do_')
            plot_type: The type of plot ('individual', 'progressive', 'grid_2x2')
            
        Returns:
            Path object to the nested directory.
        """
        path = cls.SEASONAL_PLOTS_DIR / parameter / plot_type
        path.mkdir(parents=True, exist_ok=True)
        return path

if __name__ == "__main__":
    # Self-test when run directly
    print(f"Project Root: {ProjectPaths.PROJECT_ROOT}")
    print(f"Data Dir: {ProjectPaths.DATA_DIR} (Exists: {ProjectPaths.DATA_DIR.exists()})")
    print(f"Figures Dir: {ProjectPaths.FIGURES_DIR} (Exists: {ProjectPaths.FIGURES_DIR.exists()})")
    
    status = ProjectPaths.verify_symlinks()
    print("\nSymlink Status:")
    for name, info in status.items():
        print(f"  {name}: Symlink={info['is_symlink']}, Exists={info['exists']}, Target={info['target']}")

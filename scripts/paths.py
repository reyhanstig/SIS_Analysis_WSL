from pathlib import Path
import os

class ProjectPaths:
    """
    Centralized path management for the project.

    INSTRUCTIONS FOR WRITING PATHS:
    ------------------------------
    Always use this class to handle file paths instead of hardcoding strings.
    This ensures compatibility across Windows and WSL/Linux.

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

    # Data Directories
    DATA_DIR = PROJECT_ROOT / "data"
    RAW_DATA_DIR = DATA_DIR / "raw" / "environmental_data"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    BOUNDARIES_DIR = DATA_DIR / "boundaries"
    
    # Processed Files
    MERGED_DATA_FILE = PROCESSED_DATA_DIR / "merged_gdf.feather"

    # Reference Files
    SOURCES_DIR = PROJECT_ROOT / "sources"
    WATER_MANUAL_PATH = DATA_DIR / "raw" / "environmental_manual" / "water_manual.xls"

    # Output Directories
    REPORTS_DIR = PROJECT_ROOT / "reports"
    FIGURES_DIR = REPORTS_DIR / "figures"
    
    @classmethod
    def ensure_directories(cls):
        """Ensure that critical output directories exist."""
        cls.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.FIGURES_DIR.mkdir(parents=True, exist_ok=True)

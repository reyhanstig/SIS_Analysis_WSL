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
    
    # Processed Files
    MERGED_DATA_FILE = PROCESSED_DATA_DIR / "merged_gdf.feather"

    # Reference Files
    SOURCES_DIR = PROJECT_ROOT / "sources"
    
    # Corrected path for water manual based on data structure
    # Previously in sources/, now aligned with data structure
    WATER_MANUAL_PATH = DATA_DIR / "raw" / "environmental_manual" / "water_manual.xls"

    # Output Directories
    REPORTS_DIR = PROJECT_ROOT / "reports"
    
    # Figures Directory (Symlink in Project Root)
    FIGURES_DIR = PROJECT_ROOT / "figures"
    
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

if __name__ == "__main__":
    # Self-test when run directly
    print(f"Project Root: {ProjectPaths.PROJECT_ROOT}")
    print(f"Data Dir: {ProjectPaths.DATA_DIR} (Exists: {ProjectPaths.DATA_DIR.exists()})")
    print(f"Figures Dir: {ProjectPaths.FIGURES_DIR} (Exists: {ProjectPaths.FIGURES_DIR.exists()})")
    
    status = ProjectPaths.verify_symlinks()
    print("\nSymlink Status:")
    for name, info in status.items():
        print(f"  {name}: Symlink={info['is_symlink']}, Exists={info['exists']}, Target={info['target']}")

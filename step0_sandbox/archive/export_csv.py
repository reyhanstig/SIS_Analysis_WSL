import pandas as pd
from utils.paths import ProjectPaths

def save_to_processed(df: pd.DataFrame, filename: str) -> None:
    """
    Saves a dataframe to the processed data directory as a CSV.
    
    Args:
        df (pd.DataFrame): The dataframe to save.
        filename (str): The name of the file (e.g., 'dist_matrix_km.csv').
    """
    # Ensure the filename ends with .csv
    if not filename.endswith('.csv'):
        filename += '.csv'
        
    # Construct the absolute path using ProjectPaths
    output_path = ProjectPaths.PROCESSED_DATA_DIR / filename
    
    # Save the dataframe
    try:
        df.to_csv(output_path)
        print(f"Successfully saved to: {output_path}")
    except Exception as e:
        print(f"Error saving file: {e}")

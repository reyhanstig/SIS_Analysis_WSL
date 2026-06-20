# step1_data_extraction/main.py
import logging
from .process1_extract_spatial import main as extract_spatial_main

def main():
    logging.info("Starting step 1 data extraction processes...")
    try:
        extract_spatial_main()
        logging.info("Step 1 data extraction completed successfully.")
        return 0
    except Exception as e:
        logging.error(f"Error during step 1 extraction: {e}")
        return 1

if __name__ == "__main__":
    main()

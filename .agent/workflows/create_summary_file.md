---
description: Create a summary text file describing the metadata, content, shape, and structure of a specified data file or data folder.
---

# Create Data Summary File

This workflow guides the agent through inspecting a specified data file or data folder (e.g., PDF reports, CSV files, raw data directories) and generating a structured summary text file (`pdf_summary.txt` or `<data_name>_summary.txt`) in the same directory.

## Prerequisites
- Accessible files or directories in the project workspace.
- The `sis_analysis` conda environment (or equivalent python interpreter with `pdfplumber`, `pandas`, and standard library utilities).

## Steps

### 1. Identify Target Input
- Check the user request for:
  - An absolute or relative path to a specific data file (e.g., `.pdf`, `.csv`, `.feather`, `.xlsx`).
  - An absolute or relative path to a data folder containing multiple files.
- If not provided, prompt the user:
  > "Please provide the path to the data file or folder you want to inspect and summarize."

### 2. Inspect Target Content
Determine the type of target input and run appropriate inspections:

#### Case A: If target is a Data Folder
- List all files and subdirectories using `list_dir` or script utilities.
- For each file, record the filename, file type (extension), and size in bytes.
- Identify the primary files (e.g., raw PDFs, metadata CSVs, data tables).

#### Case B: If target is a PDF Document
- Open the PDF and read its basic properties (number of pages).
- Scan page headers/titles to reconstruct the table of contents and identify major sections.
- Identify data grids or tables embedded in the document.
- Note any text encoding or layout issues (such as reversed right-to-left character strings, newline offsets, or merged grid cell layouts).

#### Case C: If target is a CSV/Feather/Excel File
- Load the file using pandas inside the python environment.
- Extract basic metadata:
  - Dimension (number of rows and columns).
  - List of columns and their respective data types (dtypes).
  - Count of non-null values for each column.
  - Presence of special markers or remarks.
- Print a small head preview (first 5 to 10 rows).

### 3. Generate Summary Text Content
Create a structured text content containing the following sections:

1. **Title / Source Info**: Filename/directory name, file size, organization/source context.
2. **Summary of Content**: A narrative describing what the data represents (e.g., survey area, date range, parameters observed).
3. **Major Sections / Files list**:
   - For folders: list of contained files with their sizes and purposes.
   - For PDFs: table of contents with page ranges and section titles.
4. **Data Shapes and Structures**:
   - Detailed column-by-column schema and description (names, types, descriptions, units).
   - Overall row/record count.
5. **Data Quality and Extraction Notes**: Document any known issues (e.g., missing values/hyphens, extraction coordinate offsets, layout workarounds).

### 4. Save and Verify Summary File
- Define the output path in the same directory as the target input:
  - If target was `h28-all.pdf`, the output is `pdf_summary.txt`.
  - If target was `my_dataset.csv`, the output is `my_dataset_summary.txt`.
  - If target was a folder, the output is `folder_summary.txt`.
- Write the summary text file using the `write_to_file` tool.
- Verify that the summary file has been created successfully and that the formatting matches the guidelines.

---
description: Workflow to read, load, and perform initial analysis on CSV or Feather files using the sis_analysis conda environment.
---

1. **Identify the target file**:
   - Check if the user has specified a CSV or Feather file path (extensions: `.csv`, `.feather`).
   - If not, ask the user to provide the absolute path to the file they want to analyze.

2. **Environment Setup (sis_analysis)**:
   - Ensure operations are performed within the `sis_analysis` conda environment.
   - **Check for `conda` availability**:
     - Run `conda --version`.
     - If `conda` is not found, attempt to locate it in common directories (e.g., `C:\Users\<User>\anaconda3\condabin\conda.bat`, `~/anaconda3/bin/conda`).
     - Use the full path to the `conda` executable for all subsequent commands if it is not in the system PATH.
   - Check if the necessary libraries (`pandas`, `matplotlib`, `seaborn`, `pyarrow`) are installed in `sis_analysis`. 
   - You can verify this by running: `conda list -n sis_analysis` (prepending the full path to conda if needed).
   - If any are missing, propose a command to install them in the environment:
     ```bash
     conda install -n sis_analysis pandas matplotlib seaborn pyarrow -y
     # OR if using pip within the environment
     conda run -n sis_analysis pip install pandas matplotlib seaborn pyarrow
     ```

3. **Data Loading and Analysis**:
   - Create a temporary Python script to load the CSV and print basic information.
   - Execute the script using the `sis_analysis` environment:
     ```bash
     conda run -n sis_analysis python <path_to_script>
     # Or using full path if needed:
     <path_to_conda> run -n sis_analysis python <path_to_script>
     ```
   - The script should perform the following:
     - Import pandas.
     - Detect file extension.
     - Load the file:
       - If CSV: `df = pd.read_csv('path/to/file.csv')`
       - If Feather: `df = pd.read_feather('path/to/file.feather')`.
     - Print the head: `print(df.head())`.
     - Print the info: `print(df.info())`.
     - Print summary statistics: `print(df.describe())`.

4. **Review and Report**:
   - Examine the output of the analysis.
   - Summarize the findings to the user (e.g., number of rows/columns, column names, missing values, data types).
   - Ask the user if they would like to proceed with any specific cleaning, deeper analysis, or visualization based on these initial findings.

---
name: Workspace Evaluation
description: Procedure for scanning a workspace and generating a comprehensive environment report with improvement recommendations.
---

# Workspace Evaluation Skill

This skill outlines the standard operating procedure for evaluating a codebase environment. Use this to quickly assess the health, organization, and documentation standards of a project workspace.

## 1. Objective
To generate a comprehensive Markdown report detailing the current state of the workspace and providing a structured list of actionable improvements and optimizations.

## 2. Scanning Procedure

### Step 2.1: Run Metadata Extraction
Write and execute a lightweight Python script to traverse the directory tree and extract metadata without loading every file fully into memory. 

- **Target Files**: `.py` (Python scripts), `.ipynb` (Jupyter notebooks), `.md` (Markdown/Reports).
- **Exclusions**: Ignore standard directories like `.git`, `.venv`, `__pycache__`, `node_modules`, `data`, and `figures`.
- **Extraction Rules**:
  - **Python (`.py`)**: Use the `ast` module to safely extract the file docstring, list of imports, top-level functions, and check for `SyntaxError`.
  - **Notebooks (`.ipynb`)**: Parse as JSON. Count the numbers of total cells, code cells, and markdown cells. Extract the contents of the very first markdown cell to see if the notebook has a proper preamble/header.
  - **Markdown (`.md`)**: Count the number of lines and extract the headers (`#`) to gauge the document structure.

Save the extracted metadata into a temporary JSON file (e.g., `/tmp/workspace_scan.json`).

### Step 2.2: Aggregation and Analysis
Read the compiled JSON metadata to aggregate insights:
1. **Summary Statistics**: Count the total number of scripts, notebooks, and markdown reports.
2. **File Organization**: Identify misplaced files (e.g., `test_*.py` files sitting in the root directory instead of a `tests/` folder). Identify leftover artifact files (e.g., `.py` versions of notebooks inside a `notebooks/` directory).
3. **Health & Documentation**: Find scripts missing top-level docstrings and notebooks missing introductory markdown headers. Identify files with syntax errors.

## 3. Reporting

Generate a final Markdown report (e.g., `reports/workspace_report_{ddmmyy}.md`) using either an LLM natively or a custom python script.

The report must contain two main sections:

### Section 1: Current State of the Workspace
- List the summary statistics and file counts.
- Document any organizational anti-patterns (e.g., root tests, leftover artifacts).
- Highlight documentation gaps (missing docstrings, empty notebook preambles).
- Note any direct syntax errors or parsing failures.

### Section 2: Recommended Improvements and Optimizations
Propose concrete actions the user can take to improve the codebase. These generally include:
- **Directory Structure reorganizations**: (e.g., moving tests, cleaning output folders, archiving old files).
- **Code Quality standards**: (enforcing docstrings in key pipeline scripts).
- **Automations**: (suggest pre-commit hooks or `make clean` scripts to deal with messy output cells or leftover artifacts).

## Example Final Deliverables
- `/tmp/workspace_scan.json`: Raw extracted metadata.
- `reports/workspace_report_MMDDYY.md`: The finalized comprehensive report.

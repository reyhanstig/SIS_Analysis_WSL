Here is the powerpoint presentation converted into a professional guide document format:

# Python Working Directory and File Management Guide

**Author:** Tsuchiya

## 1. Directory Management Basics

Understanding standard directory types is crucial for effective navigation and file management:

* **Home Directory (`/home/"User Name"`):** This is the default directory you are placed in upon logging into the shell. You can navigate to it using the `cd` command. Note that `home` is not the same as the Home directory.
* **Root Directory (`/`):** Represented by a slash, this is the root of the file system. You can navigate to it using `cd /`. Unless you are an advanced user, you should avoid editing the Root directory.
* **Current Directory:** This is the directory you are currently operating in. You can verify your current location using the `pwd` command. In relative paths, it is represented by the `.` symbol.

## 2. Working Directory Setup and Structure

* **Basic Rule:** Do not place files directly in your Home directory; only place directories there.
* **Creating Working Directories:** Create dedicated directories for your tasks (e.g., `mkdir /home/"User name"/working`). Examples of proper naming include `working`, `master_research`, or `RA_job`.
* **Hierarchy Overview:** A standard working directory should contain the following structure:
* `README.txt`: A text file describing the directory's structure.
* `step1_xxx`, `step2_xxx`: Directories designated for experimental code.
* `utils`: A directory specifically for Python utility scripts.


* **README Documentation:** Ensure the `README.txt` is written clearly so that anyone can understand it. For example, document that `Step1_xxx` contains the satellite data acquisition API, and `Step2_xxx` contains satellite data preprocessing.

## 3. Project Sub-Directory Structure

Within individual project or step directories (e.g., `step1_xxx`), maintain a standardized internal hierarchy:

* `__init__.py`: Uses double underscores to allow Python to recognize the directory as a module.
* `__main__.py`: Serves as the module's entry point.
* `main.py`: The primary execution file.
* `utils`: A subdirectory for step-specific utility scripts.
* `step1_parameter.csv`: A parameter file dedicated to this specific step.
* `process1_xxx_yyy_zzz.py`: The actual Python source code files.
* `log_process1.txt`: The corresponding log file for the processes.

## 4. File Management and Coding Practices

* **Naming Conventions:** File names can be long and should include specific details. Examples include `process1_calc_sst_form_satellite.py` or `process2_draw_sst_scatter_plot.py`.
* **Process Scope:** Keep the results of a single process as minimal as possible. This significantly simplifies the maintenance and management of the source code.

## 5. Parameter Management

* **Avoid Hardcoding:** Do not hardcode variables directly within your scripts (e.g., avoid writing `start_month = 1`, `start_date = 1`).
* **Best Practice:** Load parameters from a CSV file (e.g., using `pandas`).
* *Example:* `start_month = process1_parameter["month"]` and `start_date = process1_parameter["date"]`.


* **CSV File Formatting:** Structure your CSV parameter files logically with columns for `name`, `value`, and `type`.
* *Example Row:* `process1_month, 1, int`.
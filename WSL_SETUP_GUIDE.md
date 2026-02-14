# Master WSL Migration Plan

> **Note:** You are currently working on Windows. Use this guide only when you are ready to permanently move your workflow to WSL (Ubuntu).

## Phase 1: Preparation (On Windows)
Before you move, ensure your project is clean and ready.

1.  **Push Everything**: Run `git push` to ensure your latest code is safe on GitHub.
2.  **Push Data**: If you have new data, run `dvc push`.
3.  **Check for Hardcoded Paths**:
    *   Scan your notebooks for any path starting with `C:\` or `c:\`.
    *   Change them to use relative paths or the `ProjectPaths` helper in `scripts/paths.py`.
    *   *Example bad*: `pd.read_csv(r"c:\Users\ex\data.csv")`
    *   *Example good*: `pd.read_csv("../data/processed/data.csv")`

## Phase 2: The Move (Transferring Files)
Perform these steps inside your **WSL Terminal** (Ubuntu).

1.  **Go to Home Directory**:
    ```bash
    cd ~
    ```
2.  **Copy Files**:
    *   We use `sudo` to bypass Windows "Read-Only" permission issues with `.git` files.
    ```bash
    # Replace 'reyha' with your Windows username if different
    sudo cp -r /mnt/c/Users/reyha/Documents/SIS_Analysis .
    ```
3.  **Fix Permissions**:
    *   Transfer ownership from 'root' to your user so you can edit files.
    ```bash
    sudo chown -R $USER:$USER SIS_Analysis
    ```
4.  **Enter the Folder**:
    ```bash
    cd SIS_Analysis
    ```

## Phase 3: System & Environment Setup

1.  **Install Conda (if missing)**:
    ```bash
    # Only if 'conda' command is not found
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
    bash ~/miniconda.sh -b -u -p ~/miniconda3
    rm ~/miniconda.sh
    ~/miniconda3/bin/conda init bash
    source ~/.bashrc
    ```
2.  **Create Environment**:
    ```bash
    conda env create -f environment.yml
    conda activate sis_analysis
    ```

## Phase 4: Git & Authentication
Since this is a new "computer" (virtually), you need to re-authenticate.

1.  **Fix Git Ownership**:
    ```bash
    git config --global --add safe.directory "*"
    ```
2.  **Configure Identity**:
    ```bash
    git config --global user.name "Your Name"
    git config --global user.email "your.email@example.com"
    ```
3.  **Setup SSH for GitHub** (Recommended):
    ```bash
    # Generate key
    ssh-keygen -t ed25519 -C "your.email@example.com"
    # (Press Enter for all prompts)
    
    # Add to agent
    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/id_ed25519
    
    # View key (copy this output to GitHub Settings > SSH Keys)
    cat ~/.ssh/id_ed25519.pub
    ```
4.  **Setup DVC (Google Drive)**:
    ```bash
    dvc pull
    ```
    *   Click the link provided in the terminal to authenticate with Google Drive.
    *   Paste the verification code back into the terminal.

## Phase 5: Verification & Cleanup

1.  **Test a Notebook**:
    *   Launch VS Code: `code .`
    *   Open `notebooks/01_Data_Processing.ipynb`.
    *   Select Kernel: `sis_analysis`.
    *   Run the imports cell.
2.  **Check Scripts**:
    *   Run a script to ensure paths work: `python scripts/convert_to_geojson.py -h`
3.  **Archive Windows Folder**:
    *   Once you are successfully working in WSL, rename your old Windows folder (e.g., `SIS_Analysis_ARCHIVED`) to avoid confusion.
    *   **Do not** delete it immediately until you are 100% sure everything works in WSL.

## Troubleshooting Common Issues

*   **"Permission Denied"**: Run `sudo chown -R $USER:$USER .` inside the project folder.
*   **"Command not found: conda"**: Run `source ~/.bashrc`.
*   **"Dubious ownership"**: Run the `safe.directory` command in Phase 4.

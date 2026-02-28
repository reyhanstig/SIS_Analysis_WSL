#!/bin/bash

# Script to fix DVC setup and synchronize structure in WSL

PROJECT_ROOT=$(pwd)
WINDOWS_PROJECT_ROOT="/mnt/c/Users/reyha/Documents/SIS_Analysis_Windows"
WINDOWS_DVC_REMOTE="/mnt/c/Users/reyha/Documents/SIS_Analysis_DVC_Remote"

echo "Running DVC Setup Fix for WSL..."
echo "Project Root: $PROJECT_ROOT"
echo "Windows Project Root: $WINDOWS_PROJECT_ROOT"

# 1. DVC Check (Optional)
if ! command -v dvc &> /dev/null; then
    echo "Note: DVC is not installed. Data management should be done in Windows."
fi

# 2. Fix Data Symlink
DATA_LINK="$PROJECT_ROOT/data"
TARGET_DATA="$WINDOWS_PROJECT_ROOT/data"

if [ -L "$DATA_LINK" ]; then
    CURRENT_TARGET=$(readlink "$DATA_LINK")
    if [ "$CURRENT_TARGET" != "$TARGET_DATA" ]; then
        echo "Updating data symlink..."
        rm "$DATA_LINK"
        ln -s "$TARGET_DATA" "$DATA_LINK"
        echo "Linked $DATA_LINK -> $TARGET_DATA"
    else
        echo "Data symlink is already correct."
    fi
elif [ -d "$DATA_LINK" ]; then
    echo "Warning: 'data' is a directory, not a symlink. Skipping link creation to avoid data loss."
else
    echo "Creating data symlink..."
    ln -s "$TARGET_DATA" "$DATA_LINK"
    echo "Linked $DATA_LINK -> $TARGET_DATA"
fi

# 3. specific folders to link from Windows (if they don't exist in WSL)
FOLDERS=("00_Heavy_Assets" "notes" "sources")

for FOLDER in "${FOLDERS[@]}"; do
    WSL_PATH="$PROJECT_ROOT/$FOLDER"
    WIN_PATH="$WINDOWS_PROJECT_ROOT/$FOLDER"
    
    if [ ! -e "$WSL_PATH" ]; then
        if [ -d "$WIN_PATH" ]; then
            ln -s "$WIN_PATH" "$WSL_PATH"
            echo "Linked $WSL_PATH -> $WIN_PATH"
        else
            echo "Warning: Source folder $WIN_PATH does not exist explicitly."
        fi
    else
        echo "$FOLDER already exists in WSL. Skipping."
    fi
done

# 4. Update .dvc/config for WSL path
DVC_CONFIG="$PROJECT_ROOT/.dvc/config"
if [ -f "$DVC_CONFIG" ]; then
    # logical check: if it contains C:/ replace it
    if grep -q "C:/" "$DVC_CONFIG"; then
        echo "Updating .dvc/config remote path..."
        # Backup
        cp "$DVC_CONFIG" "$DVC_CONFIG.bak"
        # Use sed to replace the windows path with the WSL path regex or direct string replacement
        # The specific line is: url = C:/Users/reyha/Documents/SIS_Analysis_DVC_Remote
        # We want: url = /mnt/c/Users/reyha/Documents/SIS_Analysis_DVC_Remote
        
        # Simple replacement of C:/Users with /mnt/c/Users
        sed -i 's|url = C:/Users|url = /mnt/c/Users|g' "$DVC_CONFIG"
        echo ".dvc/config updated."
    else
        echo ".dvc/config appears to already use Unix-style paths."
    fi
else
    echo ".dvc/config not found!"
fi

echo "Setup check complete."

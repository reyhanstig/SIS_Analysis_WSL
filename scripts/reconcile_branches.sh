#!/bin/bash
# Reconcile Git Branches for Hybrid DVC Workflow

# Ensure we are in the project root
cd "$(dirname "$0")/.."

echo "Starting branch reconciliation..."

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Stashing uncommitted changes..."
    git stash push -m "Automatic stash for branch reconciliation"
    HAS_STASH=true
else
    HAS_STASH=false
fi

# Pull with rebase to keep linear history (Windows data updates -> Your code updates)
echo "Pulling with rebase..."
if git pull --rebase; then
    echo "Rebase successful."
else
    echo "Error: Rebase failed due to conflicts. Please resolve them manually."
    exit 1
fi

# Restore stash if needed
if [ "$HAS_STASH" = true ]; then
    echo "Restoring stashed changes..."
    if git stash pop; then
        echo "Stash restored successfully."
    else
        echo "Warning: Stash pop had conflicts. Please resolve them."
    fi
fi

echo "Git branch reconciliation complete. You are now synced with Windows data updates."

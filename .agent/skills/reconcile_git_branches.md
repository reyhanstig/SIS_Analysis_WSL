---
name: Reconcile Git Branches for DVC Workflow
description: A skill to handle git branch divergence when pulling data updates in a hybrid DVC workflow.
---

# Reconcile Git Branches

This skill automates the reconciliation of git branches when you encounter divergent branches after running `git pull` (common in hybrid Windows/WSL DVC workflows).

## Context
In this hybrid workflow:
- **Windows** updates data and pushes `data.dvc`.
- **WSL** updates code and pushes scripts/notebooks.
- Divergence happens when both sides push changes without pulling first.

## Usage

When you see a "divergent branches" error or "Need to specify how to reconcile divergent branches", use this script.

### Automation Script
Use the `scripts/reconcile_branches.sh` script to automate this process.

```bash
# Run this in your WSL environment
./scripts/reconcile_branches.sh
```

### Manual Steps
If you prefer to do it manually:
1. **Stash Changes**: `git stash` (Save uncommitted work)
2. **Pull with Rebase**: `git pull --rebase` (Apply your local commits on top of remote changes)
3. **Pop Stash**: `git stash pop` (Restore uncommitted work)
4. **Resolve Conflicts**: If any conflicts arise, fix them in your editor, then `git add .` and `git rebase --continue`.

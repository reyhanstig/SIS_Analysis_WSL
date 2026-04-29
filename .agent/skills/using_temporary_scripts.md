# Skill: Using Temporary Scripts

## Description
This skill defines the protocol for managing temporary, helper, and scratch scripts created during analysis, debugging, or scaffolding tasks. The primary goal is to maintain a clean workspace by ensuring these temporary files are removed as soon as their purpose is fulfilled.

## Triggers
- You create a temporary script to test logic on a smaller scale before applying it to a production file (e.g., `test_join.py`, `test_logic.py`).
- You create a helper script to programmatically modify other files (e.g., `patch_notebooks.py`, `update_configs.py`).
- You create a script to scaffold or generate new Jupyter notebooks or project structures.
- You create intermediate text or data files to quickly inspect output (e.g., `tmp_output.txt`).

## Instructions
1. **Naming Convention**: When creating a temporary script, try to use prefixes like `tmp_` or `test_` so it is clearly identifiable as a scratch file, though this is not strictly required if the purpose is clear.
2. **Execution**: Run the script and verify that it accomplishes its intended task.
3. **Immediate Cleanup (CRITICAL)**: As soon as the script has successfully completed its task and is no longer needed, you **MUST** immediately delete the file from the workspace. Do not wait for the user to ask you to clean it up.
4. **Inform the User**: When you summarize your actions for the user, mention that you created a helper script to accomplish the task and subsequently deleted it to keep the workspace clean.

## Example Scenario
1. **User request**: "Update the colorbar label in these three notebooks."
2. **Action**: You create a script `patch_colorbar.py` to automate the JSON manipulation of the `.ipynb` files.
3. **Execution**: You run `python patch_colorbar.py`.
4. **Verification**: You check the git diff or notebook contents to ensure the changes were applied correctly.
5. **Cleanup**: You run `rm patch_colorbar.py` to delete the script.
6. **Response**: You inform the user: "I updated the colorbar labels across the three notebooks using a temporary helper script, which I have now removed to keep your directory clean."

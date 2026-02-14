---
description: Protocol for handling requests to modify Jupyter Notebook (.ipynb) files
---
# Jupyter Notebook Modification Protocol

AI agents should not attempt to directly modify `.ipynb` files due to their complex JSON structure and potential for corruption. Instead, follow this protocol when a user asks for changes to a notebook:

1. **Analyze the Request**: Understand what changed logic or new feature is required in the notebook.
2. **Context Retrieval**: Read the relevant parts of the notebook (if needed) to understand variable names, dataframes, and current logic. Use `view_file` to read the content but treat it as read-only.
3. **Generate Code Snippet**: Create the Python code block that achieves the user's goal.
4. **Explain the Code**: Provide a clear explanation of what the code does and where it fits in the analysis.
5. **Output to Chat**: Present the code snippet and explanation in the chat response.
   - **CRITICAL**: Do NOT use `replace_file_content` or `multi_replace_file_content` on `.ipynb` files.
   - Explicitly tell the user: "Here is the code snippet to modify/add to your notebook. Please insert it manually into a new or existing cell."

## Example Response Format

"I cannot modify the notebook directly. Here is the code snippet you need to add to your notebook:

```python
# Code goes here
import pandas as pd
# processing logic...
```

**Explanation**:
This code performs [action] by [mechanism]..."

This document serves as a master guide for any AI agent activities that takes place in this working directory.

- Any parameters for scripts are to be stored in a csv file and loaded using pandas.
- Script name, folder name, and figure name should be descriptive and clearly indicate the contents of the script or folder or figure.
- Any codes should be written in a way that it is easy to understand and maintainable. This includes proper comments and docstrings.
- Generally, one script should only produce one output. If multiple outputs are needed, then the production will take place on a different script using a loop based on the input parameters.
- Notebooks can be run as a script using the agent_notebook_utils.py. This can also enable modularity to extract and run only the required function.
- Paths shouldn't be hardcoded in scripts or notebooks. Instead, use the ProjectPaths class defined in scripts/paths.py.
- The notebook and scripts within the main pipeline steps folder should be numbered using a logical naming convention to indicate the order of execution. The numbering should also use the 10's place for the sub-steps within that step folder. and the 1's 
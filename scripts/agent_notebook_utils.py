import os
import sys
import types
import nbformat
from nbconvert import PythonExporter

def get_notebook_code(nb_path):
    """
    Reads a Jupyter Notebook and returns its raw python code.
    Markdown cells are converted to comments.
    """
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
        
        exporter = PythonExporter()
        source_code, _ = exporter.from_notebook_node(nb)
        return source_code

def convert_notebook_to_script(nb_path, py_path=None):
    """
    Converts a Jupyter Notebook to a standalone Python script.
    If py_path is not provided, it saves the file in the same directory
    with a .py extension.
    """
    source_code = get_notebook_code(nb_path)
    
    if py_path is None:
        base, _ = os.path.splitext(nb_path)
        py_path = f"{base}.py"
        
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(source_code)
    
    print(f"Successfully converted '{nb_path}' to '{py_path}'.")
    return py_path

def load_nb_as_module(nb_path):
    """
    Loads a Jupyter Notebook dynamically as a Python module.
    Useful for testing specific functions from an exploratory notebook 
    without running the entire file or extracting it manually.
    """
    source_code = get_notebook_code(nb_path)
    
    module_name = os.path.basename(nb_path).replace(".ipynb", "")
    module = types.ModuleType(module_name)
    
    # Add dummy file path to help debugging within the module
    module.__file__ = nb_path
    
    exec(source_code, module.__dict__)
    return module

import os
import ast
import json
import pkg_resources

def get_imports(file_path):
    imports = set()
    try:
        if file_path.endswith('.py'):
            with open(file_path, 'r', encoding='utf-8') as f:
                root = ast.parse(f.read(), filename=file_path)
        elif file_path.endswith('.ipynb'):
            with open(file_path, 'r', encoding='utf-8') as f:
                nb = json.load(f)
                code_cells = [cell['source'] for cell in nb['cells'] if cell['cell_type'] == 'code']
                code = '\n'.join([''.join(source) for source in code_cells])
                root = ast.parse(code, filename=file_path)
        else:
            return imports

        for node in ast.walk(root):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    
    return imports

def main():
    root_dir = '/home/reyha/SIS_Analysis_WSL'
    all_imports = set()
    
    for subdir, dirs, files in os.walk(root_dir):
        if '.venv' in subdir or '.dvc' in subdir or '.git' in subdir:
            continue
        for file in files:
            if file.endswith(('.py', '.ipynb')):
                file_path = os.path.join(subdir, file)
                imports = get_imports(file_path)
                all_imports.update(imports)

    stdlib_modules = {
        'os', 'sys', 're', 'json', 'math', 'datetime', 'time', 'random', 'glob',
        'collections', 'itertools', 'functools', 'pathlib', 'shutil', 'subprocess',
        'pickle', 'typing', 'enum', 'copy', 'io', 'csv', 'argparse', 'logging',
        'warnings', 'tempfile', 'unittest', 'contextlib', 'platform', 'inspect',
        'traceback', 'threading', 'multiprocessing', 'concurrent', 'urllib', 'http',
        'xml', 'html', 'email', 'mimetypes', 'sqlite3', 'uuid', 'base64', 'hashlib',
        'hmac', 'secrets', 'tarfile', 'zipfile', 'zlib', 'gzip', 'bz2', 'lzma',
        'socket', 'ssl', 'select', 'selectors', 'asyncio', 'signal', 'mmap', 'ctypes',
        'abc', 'atexit', 'gc', 'weakref', 'site', 'code', 'codeop', 'pdb', 'faulthandler',
        'tracemalloc', 'distutils', 'ensurepip', 'venv', 'zipapp', 'ast', 'dis', 'token',
        'keyword', 'tokenize', 'tabnanny', 'pyclbr', 'py_compile', 'compileall',
        'pydoc', 'doctest', 'test', 'setuptools', 'pkg_resources', '__future__'
    }

    third_party_imports = sorted(list(all_imports - stdlib_modules))
    
    print("Found imports:")
    for imp in third_party_imports:
        print(imp)

if __name__ == "__main__":
    main()

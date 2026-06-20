import os
import nbformat
from nbconvert import PythonExporter
import types
import sys


def load_nb_as_module(nb_path):
    with open(nb_path,"r",encoding="utf-8") as f:
        nb = nbformat.read(f,as_version=4)

        #notebookをpythonに変換
        exporter = PythonExporter()
        source_code, _ = exporter.from_notebook_node(nb)

        #pythonモジュールを作成
        module = types.ModuleType("module")
        exec(source_code, module.__dict__)

    return module
#end def

#データ分析用関数のpath
func_base_dir = "/home/t-yutaka/working/git_home/practice/temp_code_place/s1_function/step6_slick_distribution"
if __name__ == "__main__":
    #関数ファイルの読み込みと起動


    prog6 = load_nb_as_module(os.path.join(func_base_dir,"step6_process6_calc_wind_speed_interpolated.ipynb"))
    for year in range(2024,2025):

        prog6.process6_calc_wind_speed_interpolated(year,JMA_FLUG=True)
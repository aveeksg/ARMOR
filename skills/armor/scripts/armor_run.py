import runpy, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # puts scripts/ on sys.path
runpy.run_module("armor", run_name="__main__", alter_sys=True)

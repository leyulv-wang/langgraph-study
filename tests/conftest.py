import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

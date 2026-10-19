"""Where kalo keeps user files: overlays/ (served as-is) and data/ (generated caches)."""
import sys
from pathlib import Path

# Next to kalo.exe when frozen (PyInstaller unpacks code to a temp dir), else the project root.
APP_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
OVERLAYS_DIR = APP_DIR / 'overlays'
DATA_DIR = APP_DIR / 'data'

"""Ensure tests can import modules from the repo root."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Tests disable the sample autoload so they don't try to scan sample/videos.
os.environ.setdefault("ANNOTATION_GUI_NO_AUTOLOAD", "1")

"""
Test configuration to ensure project modules are importable without PYTHONPATH tweaks.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.abspath(PROJECT_ROOT))

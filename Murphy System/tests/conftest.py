"""
Test configuration for Murphy System.

Adds src/ to sys.path so modules can be imported without
manual PYTHONPATH manipulation.
"""

import os
import sys

# Add src/ to the Python path
_src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
_src_dir = os.path.abspath(_src_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

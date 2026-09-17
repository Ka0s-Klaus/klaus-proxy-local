#!/bin/bash
# Klaus Monitor TUI launcher - Workaround for PATH issues

cd "$(dirname "$0")"
export PYTHONPATH=src
python3.13 << 'PYTHON'
import sys
sys.path.insert(0, 'src')
from Klaus_proxy_local.monitor.app import KlausMonitorApp

try:
    app = KlausMonitorApp()
    app.run()
except ImportError as e:
    print(f"Error: {e}")
    print("\nRequirements:")
    print("  - Python 3.13+")
    print("  - pip install -e .")
    print("  - textual>=0.70.0")
    sys.exit(1)
PYTHON

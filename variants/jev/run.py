#!/usr/bin/env python3
"""Run the parallel variant from this checkout without installing packages."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ally_analyzer_jev.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

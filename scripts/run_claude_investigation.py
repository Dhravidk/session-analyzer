#!/usr/bin/env python3
"""Development entry point for the shipped managed Claude workflow."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ally_analyzer.claude_runner import main
if __name__ == '__main__': raise SystemExit(main())

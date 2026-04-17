#!/usr/bin/env python
"""Entry point so `python -m unigate` works."""
import sys
from unigate.cli import main

if __name__ == "__main__":
    sys.exit(main())
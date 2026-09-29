#!/usr/bin/env python3
"""Compatibility wrapper for deployments running respondd.py from a checkout.

New deployments should install the package and use the ``unified-respondd`` command.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from unified_respondd.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

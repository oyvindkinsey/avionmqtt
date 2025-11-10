"""
Entry point when running as a module: python -m avionmqtt
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

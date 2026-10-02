"""
Package entrypoint for SECONDShift CLI
Supports execution via: python -m secondshift <subcommand>
"""

import sys
from secondshift.cli import main

if __name__ == "__main__":
    main()

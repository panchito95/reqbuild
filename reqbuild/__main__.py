"""Allow running as: python -m reqbuild"""
import sys
from .cli import main

sys.exit(main())

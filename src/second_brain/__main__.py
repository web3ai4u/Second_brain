"""Allow running Second Brain as: python -m second_brain"""
from .cli import main
import sys

sys.exit(main())

"""`python -m fin_env.generate --seed 4217 --config configs/dev/x.json --out episodes/dev`"""
import sys

from .generator import main

if __name__ == "__main__":
    sys.exit(main())

"""Legacy CLI alias: python -m speech987 is still supported."""
from unscript.__main__ import main, _evaluate

if __name__ == "__main__":
    raise SystemExit(main())

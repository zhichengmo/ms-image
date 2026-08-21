"""Runtime worker package bootstrap.

Workers import Runtime packages through the repository-root
``apps.runtime`` namespace.
"""

from pathlib import Path
import sys


# /repo/apps/runtime/workers/__init__.py -> /repo
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


__all__: tuple[str, ...] = ()

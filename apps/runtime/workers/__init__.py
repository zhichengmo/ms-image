"""Runtime worker package bootstrap.

Workers keep importing the single Runtime ``app`` package.  Add the Runtime
directory when a worker is launched from the repository root through its
fully-qualified ``apps.runtime.workers`` module path.
"""

from pathlib import Path
import sys


RUNTIME_ROOT = Path(__file__).resolve().parent.parent
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


__all__: tuple[str, ...] = ()

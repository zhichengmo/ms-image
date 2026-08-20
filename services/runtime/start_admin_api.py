#!/usr/bin/env python3
from pathlib import Path
import sys

import uvicorn


RUNTIME_ROOT = Path(__file__).resolve().parent
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


if __name__ == "__main__":
    # Production-like standalone admin entrypoint; reload belongs only to a
    # developer shell and can otherwise create an untracked second process.
    uvicorn.run(
        "main:admin_app",
        app_dir=str(RUNTIME_ROOT),
        host="0.0.0.0",
        port=8001,
        reload=False,
    )

#!/usr/bin/env python3
from pathlib import Path
import sys

import uvicorn


RUNTIME_ROOT = Path(__file__).resolve().parent
REPO_ROOT = RUNTIME_ROOT.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


if __name__ == "__main__":
    uvicorn.run(
        "apps.backend.services.runtime.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )

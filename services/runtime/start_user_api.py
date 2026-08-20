#!/usr/bin/env python3
from pathlib import Path
import sys

import uvicorn


RUNTIME_ROOT = Path(__file__).resolve().parent
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        app_dir=str(RUNTIME_ROOT),
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

#!/usr/bin/env python3
import uvicorn

if __name__ == "__main__":
    # Production-like standalone admin entrypoint; reload belongs only to a
    # developer shell and can otherwise create an untracked second process.
    uvicorn.run("main:admin_app", host="0.0.0.0", port=8001, reload=False)

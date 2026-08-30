#!/usr/bin/env python3
"""Issue a short-lived RS256 bearer token for the local dev Runtime API.

Usage: python scripts/dev/issue_dev_token.py [scope ...]
Default scope: imaging:run
Prints the token to stdout only (never persisted).
"""

import sys
import time

import jwt
from pathlib import Path

KEYS_DIR = Path(__file__).resolve().parent / "keys"
SCOPES = " ".join(sys.argv[1:]) or "imaging:run"
now = int(time.time())
payload = {
    "sub": "codex-local-e2e",
    "scope": SCOPES,
    "iss": "ms-image",
    "aud": "ms-image-api",
    "iat": now,
    "exp": now + 3600,
}
print(jwt.encode(payload, (KEYS_DIR / "private.pem").read_text(), algorithm="RS256"))

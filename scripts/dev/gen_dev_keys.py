#!/usr/bin/env python3
"""Generate a local dev RSA keypair for ms-image Runtime API JWT.

Output: scripts/dev/keys/public.pem + private.pem
These files are runtime-local only.  Add scripts/dev/keys/ to .gitignore so
they are never committed.  The private key is only used to issue bearer
tokens for local API calls (scripts/dev/run_e2e_local.py).
"""

import rsa
from pathlib import Path

KEYS_DIR = Path(__file__).resolve().parent / "keys"


def main() -> None:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    pub, priv = rsa.newkeys(2048)
    (KEYS_DIR / "public.pem").write_bytes(pub.save_pkcs1("PEM"))
    (KEYS_DIR / "private.pem").write_bytes(priv.save_pkcs1("PEM"))
    print("wrote", KEYS_DIR / "public.pem")
    print("wrote", KEYS_DIR / "private.pem")
    print("Run scripts/dev/issue_dev_token.py to create a bearer token.")


if __name__ == "__main__":
    main()

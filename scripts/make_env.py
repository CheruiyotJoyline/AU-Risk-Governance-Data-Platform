"""Create .env from .env.example, replacing placeholder secrets with random values."""

import base64
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
example, target = ROOT / ".env.example", ROOT / ".env"

if target.exists():
    sys.exit(".env already exists; delete it first if you want new secrets.")

lines = []
for line in example.read_text().splitlines():
    if line.endswith("=change-me-fernet"):
        key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        line = line.replace("change-me-fernet", key)
    elif line.endswith("=change-me"):
        line = line.replace("change-me", secrets.token_urlsafe(24))
    lines.append(line)

target.write_text("\n".join(lines) + "\n")
print(f"Wrote {target}")

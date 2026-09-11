"""Create a git-ignored development environment with random local credentials."""
from pathlib import Path
import json
import secrets

destination = Path("deploy/.env")
if destination.exists():
    print(f"preserved existing {destination}")
else:
    values = {
        "REDIS_PASSWORD": secrets.token_urlsafe(24),
        "FSSAI_EVIDENCE_TOKEN": secrets.token_urlsafe(32),
        "FSSAI_APPROVAL_SIGNING_KEY": secrets.token_urlsafe(48),
        "FSSAI_IMPORT_SOURCE_KEYS_JSON": json.dumps({"demo-source": secrets.token_urlsafe(32)}),
        "MINIO_ROOT_USER": "fssaira-local",
        "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(32),
    }
    destination.write_text(
        "# Generated for local development; do not commit or use in production.\n"
        + "\n".join(f"{key}={value}" for key, value in values.items())
        + "\n",
        encoding="utf-8",
    )
    print(f"created {destination}")

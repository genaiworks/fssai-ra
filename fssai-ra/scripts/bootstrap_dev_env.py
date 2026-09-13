"""Create a git-ignored development environment with random local credentials."""
import json
import secrets
from pathlib import Path

destination = Path("deploy/.env")
if destination.exists():
    print(f"preserved existing {destination}")
else:
    operator_token = secrets.token_urlsafe(32)
    officer_token = secrets.token_urlsafe(32)
    second_officer_token = secrets.token_urlsafe(32)
    agent_token = secrets.token_urlsafe(32)
    values = {
        "POSTGRES_USER": "fssaira",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "POSTGRES_DB": "fssaira",
        "REDIS_PASSWORD": secrets.token_urlsafe(24),
        "FSSAI_EVIDENCE_TOKEN": secrets.token_urlsafe(32),
        "FSSAI_APPROVAL_SIGNING_KEY": secrets.token_urlsafe(48),
        "FSSAI_APPROVAL_KEY_ID": "local-development-key-1",
        "FSSAI_AUTH_MODE": "token",
        "FSSAI_AUTH_TOKENS_JSON": json.dumps({
            operator_token: {
                "subject": "platform.operator", "roles": ["platform_operator"],
            },
            officer_token: {
                "subject": "officer.one", "roles": ["student_support_officer"],
            },
            second_officer_token: {
                "subject": "officer.two", "roles": ["student_support_officer"],
            },
            agent_token: {"subject": "bounded-agent-1", "roles": ["proposer"]},
        }, separators=(",", ":")),
        "FSSAI_IMPORT_SOURCE_KEYS_JSON": json.dumps({"demo-source": secrets.token_urlsafe(32)}),
        "FSSAI_MODEL": "deterministic",
        "FSSAI_MODEL_FALLBACK": "deny",
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

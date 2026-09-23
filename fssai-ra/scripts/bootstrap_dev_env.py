"""Create a git-ignored development environment with random local credentials."""
import json
import secrets
from pathlib import Path

destination = Path("deploy/.env")

#: Secrets introduced after a .env may already exist. Missing ones are appended;
#: existing values are never changed.
LATER_KEYS = {
    # Only the import gateway and the Spark import job hold this key, so a record
    # written straight to Kafka is refused (see fssaira.envelope_mac).
    "FSSAI_IMPORT_ENVELOPE_KEY": lambda: secrets.token_urlsafe(48),
    # Only the control plane and event consumers hold this key.
    "FSSAI_EVENT_ENVELOPE_KEY": lambda: secrets.token_urlsafe(48),
}

if destination.exists():
    present = {line.split("=", 1)[0] for line in destination.read_text(encoding="utf-8").splitlines()
               if "=" in line and not line.startswith("#")}
    missing = {key: make() for key, make in LATER_KEYS.items() if key not in present}
    if missing:
        with destination.open("a", encoding="utf-8") as handle:
            handle.write("".join(f"{key}={value}\n" for key, value in missing.items()))
        print(f"added {', '.join(sorted(missing))} to existing {destination}")
    else:
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
        **{key: make() for key, make in LATER_KEYS.items()},
    }
    destination.write_text(
        "# Generated for local development; do not commit or use in production.\n"
        + "\n".join(f"{key}={value}" for key, value in values.items())
        + "\n",
        encoding="utf-8",
    )
    print(f"created {destination}")

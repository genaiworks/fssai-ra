"""Request authentication for the control plane.

Release v0.5.0 accepted ``X-FSSAI-Identity`` and ``X-FSSAI-Role`` headers and
said, correctly, that they were spoofable and must be replaced. That warning is
easy to read past, and a demonstration that anyone can approve their own award
by editing a header is not a demonstration of accountable action.

This module keeps the header adapter -- it is genuinely useful behind an
authenticated proxy that overwrites those headers -- but makes it one of three
explicit modes, refuses to use it silently, and shouts about it on ``/health``:

``token``  (default)
    Bearer tokens mapped to a subject and roles, configured out of band. Enough
    for a pilot. Tokens are compared with :func:`hmac.compare_digest`.

``header``
    Trust ``X-FSSAI-*``. Only valid when something in front of the service
    authenticates the caller and *overwrites* those headers. Selecting it
    outside a development environment is refused unless the operator also sets
    ``FSSAI_TRUST_PROXY_HEADERS=yes-i-run-an-authenticating-proxy``.

``oidc``
    Verify a JWT against a JWKS endpoint. Requires the ``auth`` extra.

Authorization is separate from authentication and stays where it belongs: the
approval role is checked by the executor against the profile, not here. This
module only establishes *who is speaking*.
"""
from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass, field

DEV_TOKENS = {
    # Non-secret development credentials. The control plane reports their use as
    # a configuration warning, and the compose file overrides them.
    "dev-operator-token": ("platform.operator", ("platform_operator",)),
    "dev-officer-token": ("officer.díaz", ("student_support_officer",)),
    "dev-agent-token": ("bounded-agent-1", ("proposer",)),
    "dev-auditor-token": ("audit.reviewer", ("auditor",)),
}


class AuthenticationError(RuntimeError):
    """Raised when a caller cannot be identified. Always a 401, never a 403."""


@dataclass(frozen=True)
class Principal:
    """An authenticated caller. Roles are claims, not permissions."""

    subject: str
    roles: tuple[str, ...]
    method: str = "token"

    def has_role(self, role: str) -> bool:
        return role in self.roles

    @property
    def role(self) -> str:
        """First role, for the single-role fields in the action protocol."""
        return self.roles[0] if self.roles else ""

    def to_dict(self) -> dict:
        return {"subject": self.subject, "roles": list(self.roles), "method": self.method}


@dataclass
class AuthConfig:
    mode: str = "token"
    tokens: dict = field(default_factory=dict)
    oidc_issuer: str = ""
    oidc_audience: str = ""
    jwks_url: str = ""
    trust_proxy_headers: bool = False
    using_development_credentials: bool = False

    def __post_init__(self) -> None:
        # An empty token map would fail every request closed, which sounds safe
        # and is actually just broken: nobody could configure the system. Fall
        # back to the published development credentials and say so loudly.
        if not self.tokens:
            self.tokens = dict(DEV_TOKENS)
            self.using_development_credentials = True

    @classmethod
    def from_env(cls) -> "AuthConfig":
        mode = os.getenv("FSSAI_AUTH_MODE", "token").lower()
        raw = os.getenv("FSSAI_AUTH_TOKENS_JSON", "")
        development = False
        if raw:
            parsed = json.loads(raw)
            tokens = {
                token: (value["subject"], tuple(value.get("roles", [])))
                for token, value in parsed.items()
            }
        else:
            tokens, development = dict(DEV_TOKENS), True
        return cls(
            mode=mode,
            tokens=tokens,
            oidc_issuer=os.getenv("FSSAI_OIDC_ISSUER", ""),
            oidc_audience=os.getenv("FSSAI_OIDC_AUDIENCE", ""),
            jwks_url=os.getenv("FSSAI_OIDC_JWKS_URL", ""),
            trust_proxy_headers=(
                os.getenv("FSSAI_TRUST_PROXY_HEADERS", "") == "yes-i-run-an-authenticating-proxy"
            ),
            using_development_credentials=development,
        )

    def warnings(self) -> list[str]:
        issues = []
        if self.mode == "header" and not self.trust_proxy_headers:
            issues.append(
                "header authentication is selected without FSSAI_TRUST_PROXY_HEADERS; "
                "callers can assert any identity"
            )
        if self.mode == "token" and self.using_development_credentials:
            issues.append("development bearer tokens are active; set FSSAI_AUTH_TOKENS_JSON")
        if self.mode == "oidc" and not self.jwks_url:
            issues.append("oidc mode selected without FSSAI_OIDC_JWKS_URL")
        return issues


class Authenticator:
    """Turns a request's credentials into a :class:`Principal`, or refuses."""

    def __init__(self, config: AuthConfig | None = None) -> None:
        self.config = config or AuthConfig.from_env()
        self._jwks_cache: dict = {}

    @property
    def warnings(self) -> list[str]:
        return self.config.warnings()

    def authenticate(self, *, authorization: str | None,
                     identity_header: str | None = None,
                     role_header: str | None = None) -> Principal:
        mode = self.config.mode
        if mode == "header":
            return self._from_headers(identity_header, role_header)
        if mode == "oidc":
            return self._from_oidc(authorization)
        return self._from_token(authorization)

    # -- modes -------------------------------------------------------------
    def _from_token(self, authorization: str | None) -> Principal:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise AuthenticationError("a bearer token is required")
        presented = authorization.split(" ", 1)[1].strip()
        for token, (subject, roles) in self.config.tokens.items():
            if hmac.compare_digest(token, presented):
                return Principal(subject, tuple(roles), method="token")
        raise AuthenticationError("the presented token is not recognised")

    def _from_headers(self, identity: str | None, role: str | None) -> Principal:
        if not self.config.trust_proxy_headers:
            raise AuthenticationError(
                "header authentication requires an authenticating proxy; set "
                "FSSAI_TRUST_PROXY_HEADERS=yes-i-run-an-authenticating-proxy to accept the risk"
            )
        if not identity or not role:
            raise AuthenticationError("X-FSSAI-Identity and X-FSSAI-Role are required")
        return Principal(identity, tuple(part.strip() for part in role.split(",") if part.strip()),
                         method="proxy-header")

    def _from_oidc(self, authorization: str | None) -> Principal:  # pragma: no cover - optional
        if not authorization or not authorization.lower().startswith("bearer "):
            raise AuthenticationError("a bearer JWT is required")
        token = authorization.split(" ", 1)[1].strip()
        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError as exc:
            raise AuthenticationError(
                "oidc mode requires the 'auth' extra: pip install 'fssaira[auth]'"
            ) from exc
        if not self._jwks_cache.get("client"):
            self._jwks_cache["client"] = PyJWKClient(self.config.jwks_url)
        key = self._jwks_cache["client"].get_signing_key_from_jwt(token).key
        try:
            claims = jwt.decode(
                token, key, algorithms=["RS256", "ES256"],
                audience=self.config.oidc_audience or None,
                issuer=self.config.oidc_issuer or None,
            )
        except Exception as exc:
            raise AuthenticationError(f"token rejected: {exc}") from exc
        roles = claims.get("roles") or claims.get("realm_access", {}).get("roles") or []
        subject = claims.get("preferred_username") or claims.get("sub", "")
        return Principal(subject, tuple(roles), method="oidc")


def require_role(principal: Principal, role: str) -> None:
    """Raise a plain ``PermissionError`` when a role claim is missing."""
    if not principal.has_role(role):
        raise PermissionError(f"role '{role}' is required for this operation")


__all__ = [
    "AuthConfig", "AuthenticationError", "Authenticator", "DEV_TOKENS",
    "Principal", "require_role",
]

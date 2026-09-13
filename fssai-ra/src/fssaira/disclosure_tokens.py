"""Disclosure grants issued by an institutional authorization server.

A teaching deployment signs grants with a shared key held by this repository.
A real institution already runs an authorization server, such as Keycloak,
Microsoft Entra ID, Okta, or a SMART on FHIR server, and should issue grants
there, under keys it controls, with its own audit and revocation.

This module verifies such grants. A grant is a JSON Web Token whose standard
claims carry holder, identifier, issuer, audience, and time, and whose single
``authorization_details`` entry of type ``fssaira_disclosure`` carries purpose,
subjects, fields, classes, basis, and emergency-access fields, in the style of
OAuth 2.0 Rich Authorization Requests (RFC 9396).

Verification is strict. Only asymmetric algorithms are accepted, so a public
key cannot be reused as an HMAC secret. Every standard claim is required. The
issuer and audience must match. A token with zero or several disclosure details
is refused rather than interpreted.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .disclosure import DisclosureGrant

DETAIL_TYPE = "fssaira_disclosure"
ASYMMETRIC = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512",
              "EdDSA")


class TokenRejected(ValueError):
    """The grant token is not acceptable; nothing is authorized by it."""


class JwtGrantVerifier:
    """Verify disclosure grant tokens against an issuer's published keys."""

    def __init__(self, *, issuer: str, audience: str, keys: dict[str, Any] | None = None,
                 jwks_url: str | None = None, algorithms: Iterable[str] = ("RS256", "ES256"),
                 leeway: float = 0.0) -> None:
        if not issuer or not audience:
            raise ValueError("a grant token verifier needs an issuer and an audience")
        if not keys and not jwks_url:
            raise ValueError("configure the issuer's public keys or its JWKS URL")
        algorithms = tuple(algorithms)
        rejected = [name for name in algorithms if name not in ASYMMETRIC]
        if rejected or not algorithms:
            raise ValueError(f"only asymmetric algorithms are accepted; refused {rejected}")
        self.issuer = issuer
        self.audience = audience
        self.algorithms = algorithms
        self.leeway = leeway
        self._keys = dict(keys or {})
        self._jwks_url = jwks_url
        self._client: Any = None

    def _signing_key(self, token: str) -> tuple[Any, str]:
        import jwt

        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenRejected(f"malformed token: {exc}") from exc
        algorithm = header.get("alg")
        if algorithm not in self.algorithms:
            raise TokenRejected(f"algorithm {algorithm!r} is not accepted")
        kid = header.get("kid") or ""
        if self._jwks_url:
            if self._client is None:
                self._client = jwt.PyJWKClient(self._jwks_url)
            try:
                return self._client.get_signing_key_from_jwt(token).key, kid
            except Exception as exc:
                raise TokenRejected(f"no trusted signing key: {exc}") from exc
        if kid in self._keys:
            return self._keys[kid], kid
        if not kid and len(self._keys) == 1:
            return next(iter(self._keys.values())), kid
        raise TokenRejected(f"signing key {kid!r} is not trusted")

    def claims(self, token: str) -> tuple[dict, str]:
        import jwt

        key, kid = self._signing_key(token)
        try:
            claims = jwt.decode(
                token, key, algorithms=list(self.algorithms), audience=self.audience,
                issuer=self.issuer, leeway=self.leeway,
                options={"require": ["exp", "iat", "sub", "jti", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenRejected(str(exc)) from exc
        return claims, kid

    def grant_from_token(self, token: str) -> DisclosureGrant:
        claims, kid = self.claims(token)
        details = [item for item in (claims.get("authorization_details") or [])
                   if isinstance(item, dict) and item.get("type") == DETAIL_TYPE]
        if len(details) != 1:
            raise TokenRejected(f"token must carry exactly one {DETAIL_TYPE} authorization detail")
        detail = details[0]

        def text(name: str, default: str | None = None) -> str:
            value = detail.get(name, default)
            if not isinstance(value, str) or (default is None and not value.strip()):
                raise TokenRejected(f"authorization detail {name!r} must be a non-empty string")
            return value

        def strings(name: str) -> frozenset:
            value = detail.get(name)
            if not isinstance(value, list) or not value or not all(
                    isinstance(item, str) and item for item in value):
                raise TokenRejected(f"authorization detail {name!r} must be a non-empty string list")
            return frozenset(value)

        break_glass = detail.get("break_glass", False)
        if not isinstance(break_glass, bool):
            raise TokenRejected("authorization detail 'break_glass' must be boolean")
        return DisclosureGrant(
            grant_id=str(claims["jti"]), holder=str(claims["sub"]), purpose=text("purpose"),
            subjects=strings("subjects"), fields=strings("fields"), classes=strings("classes"),
            issued_by=text("issued_by", str(claims["iss"])) or str(claims["iss"]),
            issued_at=float(claims["iat"]), expires_at=float(claims["exp"]),
            basis=text("basis", "declared basis"), break_glass=break_glass,
            justification=text("justification", ""),
            key_id=f"jwt:{kid}" if kid else "jwt", signature=token,
        )


def encode_grant_token(private_key: Any, *, kid: str, issuer: str, audience: str, holder: str,
                       grant_id: str, purpose: str, subjects: Iterable[str],
                       fields: Iterable[str], classes: Iterable[str], issued_by: str,
                       now: float, ttl_seconds: float, basis: str = "declared basis",
                       break_glass: bool = False, justification: str = "",
                       algorithm: str = "RS256") -> str:
    """Issue a grant token. For tests and teaching; institutions issue from their server."""
    import jwt

    payload = {
        "iss": issuer, "aud": audience, "sub": holder, "jti": grant_id,
        "iat": int(now), "exp": int(now + ttl_seconds),
        "authorization_details": [{
            "type": DETAIL_TYPE, "purpose": purpose, "subjects": sorted(subjects),
            "fields": sorted(fields), "classes": sorted(classes), "issued_by": issued_by,
            "basis": basis, "break_glass": break_glass, "justification": justification,
        }],
    }
    return jwt.encode(payload, private_key, algorithm=algorithm, headers={"kid": kid})


__all__ = ["DETAIL_TYPE", "JwtGrantVerifier", "TokenRejected", "encode_grant_token"]

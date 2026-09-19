"""Destination authorization only; transport must pin addresses and verify TLS.

This module opens no sockets and does not establish deployment network isolation.
"""
import ipaddress
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True)
class AuthorizedDestination:
    url: str
    addresses: tuple[str, ...]
    tls_identity: str
    max_bytes: int


@dataclass(frozen=True)
class DestinationPolicy:
    hostname: str
    path_prefixes: tuple[str, ...]
    max_bytes: int

    def __post_init__(self):
        if not self.hostname or self.hostname != self.hostname.lower() or type(self.max_bytes) is not int or self.max_bytes <= 0:
            raise ValueError('invalid destination policy')
        if not self.path_prefixes or any(not p.startswith('/') or not p.endswith('/') or '..' in p for p in self.path_prefixes):
            raise ValueError('explicit path prefixes required')

    def authorize(self, url, addresses, *, classifications):
        if not isinstance(url, str) or any(ord(c) <= 32 for c in url) or '\\' in url:
            raise ValueError('invalid URL')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != self.hostname or parsed.port not in (None, 443)
                or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError('destination denied')
        path = unquote(parsed.path)
        if '%' in path or '\\' in path or any(ord(c) <= 32 for c in path) or any(p in ('.', '..') for p in path.split('/')):
            raise ValueError('ambiguous path')
        if not any(path.startswith(prefix) for prefix in self.path_prefixes) or classifications:
            raise ValueError('public egress denied')
        pinned = tuple(str(ipaddress.ip_address(address)) for address in addresses)
        if not pinned or any((not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast
                                  or ipaddress.ip_address(address).is_reserved) for address in pinned):
            raise ValueError('nonpublic address')
        return AuthorizedDestination(url, pinned, self.hostname, self.max_bytes)

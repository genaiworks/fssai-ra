"""Destination authorization only; transport must pin addresses and verify TLS.

This module opens no sockets and does not establish deployment network isolation.
"""
import ipaddress
import re
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
        if (not isinstance(self.hostname, str) or not re.fullmatch(
                r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', self.hostname)
                or type(self.max_bytes) is not int or self.max_bytes <= 0):
            raise ValueError('invalid destination policy')
        if (not isinstance(self.path_prefixes, tuple) or not self.path_prefixes
                or any(not isinstance(p, str) or not p.startswith('/') or not p.endswith('/')
                       or not re.fullmatch(r'/[A-Za-z0-9_./~-]*', p)
                       or '//' in p or any(v in ('.', '..') for v in p.split('/'))
                       for p in self.path_prefixes)):
            raise ValueError('explicit path prefixes required')

    def authorize(self, url, addresses, *, classifications):
        if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) >= 127 for c in url) or '\\' in url:
            raise ValueError('invalid URL')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != self.hostname or parsed.port not in (None, 443)
                or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError('destination denied')
        # Different proxies/frameworks normalize encoded separators and matrix
        # parameters differently. Only unreserved percent escapes are accepted.
        escapes = re.findall(r'%([0-9A-Fa-f]{2})', parsed.path)
        if any(not re.fullmatch(r'[A-Za-z0-9_.~-]', chr(int(x, 16))) for x in escapes):
            raise ValueError('encoded path delimiter')
        path = unquote(parsed.path)
        if any(c in path for c in '%;?#') or '//' in path or '\\' in path or any(ord(c) <= 32 for c in path) or any(p in ('.', '..') for p in path.split('/')):
            raise ValueError('ambiguous path')
        if not any(path.startswith(prefix) for prefix in self.path_prefixes) or classifications:
            raise ValueError('public egress denied')
        pinned = tuple(str(ipaddress.ip_address(address)) for address in addresses)
        if not pinned or any((not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast
                                  or ipaddress.ip_address(address).is_reserved) for address in pinned):
            raise ValueError('nonpublic address')
        return AuthorizedDestination(url, pinned, self.hostname, self.max_bytes)

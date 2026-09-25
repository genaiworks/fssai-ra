"""Destination authorization: which address, identity and byte ceiling are approved.

This module still opens no sockets and still establishes no deployment network
isolation. It decides *what* a transport is permitted to contact.
:mod:`fssaira.integration.transport` is the component that then contacts it
under those terms and returns evidence of what actually happened on the wire.

``qualification_only`` exists so the transport harness can exercise the real
socket, TLS and byte-ceiling paths against a loopback server. A destination
authorized under that flag is marked, the marking propagates into transport
evidence, and the promotion gate refuses to treat it as production evidence.
"""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable, Set
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True)
class AuthorizedDestination:
    url: str
    addresses: tuple[str, ...]
    tls_identity: str
    max_bytes: int
    port: int = 443
    path: str = '/'
    qualification_only: bool = False


@dataclass(frozen=True)
class DestinationPolicy:
    hostname: str
    path_prefixes: tuple[str, ...]
    max_bytes: int
    port: int = 443
    qualification_only: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.hostname, str) or not re.fullmatch(
                r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', self.hostname)
                or type(self.max_bytes) is not int or self.max_bytes <= 0):
            raise ValueError('invalid destination policy')
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError('invalid destination port')
        if type(self.qualification_only) is not bool:
            raise ValueError('invalid qualification flag')
        if self.port != 443 and not self.qualification_only:
            raise ValueError('production destinations use port 443')
        if (not isinstance(self.path_prefixes, tuple) or not self.path_prefixes
                or any(not isinstance(p, str) or not p.startswith('/') or not p.endswith('/')
                       or not re.fullmatch(r'/[A-Za-z0-9_./~-]*', p)
                       or '//' in p or any(v in ('.', '..') for v in p.split('/'))
                       for p in self.path_prefixes)):
            raise ValueError('explicit path prefixes required')

    def _authorize_address(self, address: str) -> str:
        parsed = ipaddress.ip_address(address)
        if self.qualification_only:
            # The harness pins a loopback server. Nothing else is permitted even
            # here: a qualification profile must not become a private-network
            # egress path.
            if not parsed.is_loopback:
                raise ValueError('qualification transport is loopback only')
            return str(parsed)
        if not parsed.is_global or parsed.is_multicast or parsed.is_reserved:
            raise ValueError('nonpublic address')
        return str(parsed)

    def authorize(self, url: str, addresses: Iterable[str], *,
                  classifications: Set[str]) -> AuthorizedDestination:
        if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) >= 127 for c in url) or '\\' in url:
            raise ValueError('invalid URL')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != self.hostname
                or (parsed.port or 443) != self.port
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment):
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
        pinned = tuple(self._authorize_address(address) for address in addresses)
        if not pinned:
            raise ValueError('nonpublic address')
        return AuthorizedDestination(url, pinned, self.hostname, self.max_bytes,
                                     port=self.port, path=path,
                                     qualification_only=self.qualification_only)

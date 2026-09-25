"""Content-addressed supply-chain declarations; hashes are not attestation."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, ClassVar


def _hash(value: object) -> None:
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('SHA256 digest required')


@dataclass(frozen=True)
class ModelBundle:
    weights: str
    tokenizer: str
    configuration: str
    system_prompt: str
    adapters: str
    retrieval: str
    tools: str
    runtime: str
    COMPONENTS: ClassVar[tuple[str, ...]] = ('weights', 'tokenizer', 'configuration', 'system_prompt',
                                           'adapters', 'retrieval', 'tools', 'runtime')

    def __post_init__(self) -> None:
        for name in self.COMPONENTS:
            _hash(getattr(self, name))

    @classmethod
    def from_dict(cls, value: Any) -> ModelBundle:
        if not isinstance(value, dict) or set(value) != set(cls.COMPONENTS):
            raise ValueError('complete bundle required')
        return cls(**value)

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class ToolManifest:
    name: str
    server: str
    description_hash: str
    input_hash: str
    output_hash: str
    executable_hash: str
    power: int
    irreversibility: int
    effects: frozenset[str]

    def __post_init__(self) -> None:
        for field in ('description_hash', 'input_hash', 'output_hash', 'executable_hash'):
            _hash(getattr(self, field))
        if not self.name or not self.server or type(self.power) is not int or not 0 <= self.power <= 5:
            raise ValueError('invalid tool identity or power')
        if type(self.irreversibility) is not int or not 0 <= self.irreversibility <= 4:
            raise ValueError('invalid irreversibility')
        object.__setattr__(self, 'effects', frozenset(self.effects))
        if not self.effects <= {'protected_read', 'memory_write', 'external_write', 'infrastructure'}:
            raise ValueError('undeclared effect class')

    def validate_model_exposure(self) -> None:
        if self.power >= 4 or self.irreversibility >= 3 or 'infrastructure' in self.effects:
            raise ValueError('tool requires independent controlled execution')


class FrozenCatalog:
    def __init__(self, manifests: Iterable[ToolManifest]) -> None:
        self._tools: dict[str, ToolManifest] = {}
        for manifest in manifests:
            manifest.validate_model_exposure()
            if manifest.name in self._tools:
                raise ValueError('duplicate tool')
            self._tools[manifest.name] = manifest

    def check(self, manifest: ToolManifest) -> ToolManifest:
        if self._tools.get(manifest.name) != manifest:
            raise ValueError('tool catalogue drift')
        return manifest

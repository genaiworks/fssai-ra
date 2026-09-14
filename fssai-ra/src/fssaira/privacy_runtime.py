"""Opt-in, in-memory privacy reference profile. Configuration is server-owned.

This binds existing components to HTTP; it is not persistent key custody or
hardware attestation. runtime_identity must query the configured serving runtime,
never take evidence from the requesting model's payload.
"""
from collections.abc import Callable
from dataclasses import dataclass

from .encrypted_records import EncryptedRecordSource
from .model_registry import ModelRegistry
from .privacy_vault import TokenVault


@dataclass(frozen=True)
class PrivacyConfiguration:
    records: EncryptedRecordSource
    vault: TokenVault
    identity_fields: dict[str, str]
    restore_credential: str
    registry: ModelRegistry
    runtime_identity: Callable[[str], tuple[str, str]]

    def validate(self) -> None:
        if self.records._custody is not self.vault._custody:
            raise ValueError("records and token vault must use the same custody service")
        self.records._custody._authorize(self.restore_credential, "decrypt")
        if not self.registry.strict:
            raise ValueError("HTTP privacy profile requires a strict model registry")
        if not callable(self.runtime_identity):
            raise ValueError("runtime identity must be a server-owned provider")

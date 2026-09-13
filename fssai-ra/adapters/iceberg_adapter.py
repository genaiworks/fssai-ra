"""Compatibility import for the maintained Iceberg adapter.

New integrations should import :class:`fssaira.iceberg_backend.IcebergSnapshotStore`.
This module remains so links and early examples do not strand adopters on the
obsolete sketch that previously lived here.
"""
from __future__ import annotations

from fssaira.iceberg_backend import IcebergSnapshotStore as _IcebergSnapshotStore
from fssaira.iceberg_backend import load_catalog


class IcebergSnapshotStore(_IcebergSnapshotStore):
    """Backward-compatible constructor delegating to the production adapter."""

    def __init__(self, catalog_uri: str, table: str) -> None:
        catalog = load_catalog("default", uri=catalog_uri)
        super().__init__(table=table, catalog_name="default", _catalog=catalog)

from __future__ import annotations

from fieldshift.infrastructure.reference_data import load_reference_data
from fieldshift.infrastructure.settings import Settings


def test_versioned_reference_files_are_consistent() -> None:
    data = load_reference_data(Settings().reference_dir)  # raises on any broken reference
    assert "oat" in data.catalog and data.demo_farms[0].id == "sacre-coeur"

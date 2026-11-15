import os
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]   # api/ : là où sont water_use/ et exemples/
sys.path.insert(0, str(RACINE))


def pytest_configure(config):
    config.addinivalue_line("markers", "reseau: test qui interroge les vraies bases (internet)")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("WATER_USE_RESEAU") == "1":
        return
    saut = pytest.mark.skip(reason="test réseau : lancez avec WATER_USE_RESEAU=1 pour l'activer")
    for item in items:
        if "reseau" in item.keywords:
            item.add_marker(saut)


@pytest.fixture(scope="session")
def exemples():
    return RACINE / "exemples"

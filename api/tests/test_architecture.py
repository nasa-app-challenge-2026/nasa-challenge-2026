"""The layers of the server, kept by a test (same idea as architecture.test.js on the front end).

    api  ->  services  ->  contract, data_access  ->  algorithm  ->  reference

A package imports only the ones on its right, never the ones on its left. `algorithm/` is the heart
of the project: it uses the standard library, numpy and scipy and nothing else, so it can be read,
tested and reused without a web server.

`water_use` (api/water_use, the water score of a rotation) is a module of its own, beside
field_shift. One file only may import it: the adapter `data_access/field_shift_eau.py`.
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

FIELD_SHIFT_DIR = Path(__file__).resolve().parents[1] / "field_shift"

# The other packages of field_shift that each package may import.
ALLOWED_PACKAGES = {
    "reference": set(),
    "algorithm": {"reference"},
    "contract": {"algorithm", "reference"},
    "data_access": {"algorithm"},
    "services": {"algorithm", "contract", "data_access", "reference"},
    "api": {"algorithm", "contract", "data_access", "reference", "services"},
}

# The libraries (outside the standard library) that each package may use.
ALLOWED_LIBRARIES = {
    "reference": set(),
    "algorithm": {"numpy", "scipy"},
    "contract": {"pydantic"},
    "data_access": {"httpx", "numpy", "water_use"},
    "services": set(),
    "api": {"fastapi"},
}

PACKAGE_NAMES = sorted(ALLOWED_PACKAGES)

#: The only file of field_shift that knows `water_use`.
WATER_USE_ADAPTER = Path("data_access") / "field_shift_eau.py"


def imported_modules(path: Path) -> set[str]:
    """The absolute name of every module a file imports, wherever the import is written."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: write absolute imports (from field_shift...)"
            assert node.module is not None
            modules.add(node.module)
            if node.module == "field_shift":  # `from field_shift import algorithm`
                modules.update(f"field_shift.{alias.name}" for alias in node.names)
    return modules


def imports_of_package(package: str) -> Iterator[tuple[Path, str]]:
    """Every (file, module) import written in one package of field_shift."""
    for path in sorted((FIELD_SHIFT_DIR / package).rglob("*.py")):
        for module in sorted(imported_modules(path)):
            yield path.relative_to(FIELD_SHIFT_DIR), module


def package_of(module: str) -> str | None:
    """The package of field_shift that a module name points into, or None for any other module."""
    parts = module.split(".")
    if parts[0] == "field_shift" and len(parts) > 1 and (FIELD_SHIFT_DIR / parts[1]).is_dir():
        return parts[1]
    return None


def library_of(module: str) -> str | None:
    """The third-party library of a module name, or None (standard library and our own code)."""
    top = module.split(".")[0]
    if top == "field_shift" or top in sys.stdlib_module_names:
        return None
    return top


def test_every_package_has_its_place_in_the_layers() -> None:
    packages_on_disk = {
        path.name
        for path in FIELD_SHIFT_DIR.iterdir()
        if path.is_dir() and (path / "__init__.py").exists()
    }
    assert packages_on_disk == set(ALLOWED_PACKAGES), (
        "A package was added or removed: place it in ALLOWED_PACKAGES and ALLOWED_LIBRARIES."
    )


@pytest.mark.parametrize("package", PACKAGE_NAMES)
def test_a_package_imports_only_the_layers_below_it(package: str) -> None:
    violations = []
    for path, module in imports_of_package(package):
        imported = package_of(module)
        if imported not in (None, package) and imported not in ALLOWED_PACKAGES[package]:
            violations.append(f"{path} imports {module}")
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("package", PACKAGE_NAMES)
def test_a_package_uses_only_its_libraries(package: str) -> None:
    violations = []
    for path, module in imports_of_package(package):
        library = library_of(module)
        if library is not None and library not in ALLOWED_LIBRARIES[package]:
            violations.append(f"{path} imports {module}")
    assert not violations, "\n".join(violations)


def test_water_use_is_only_reached_through_its_adapter() -> None:
    importers = {
        path
        for package in PACKAGE_NAMES
        for path, module in imports_of_package(package)
        if library_of(module) == "water_use"
    }
    assert importers == {WATER_USE_ADAPTER}

"""The business core must not depend on frameworks, I/O or outer layers."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src" / "fieldshift"
FORBIDDEN = {
    "domain": (
        "fastapi",
        "pydantic",
        "httpx",
        "yaml",
        "starlette",
        "fieldshift.application",
        "fieldshift.infrastructure",
        "fieldshift.api",
    ),
    "application": (
        "fastapi",
        "httpx",
        "yaml",
        "starlette",
        "fieldshift.infrastructure",
        "fieldshift.api",
    ),
    "infrastructure": ("fastapi", "fieldshift.api"),
}


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_dependencies(layer: str) -> None:
    offenders = []
    for path in (SRC / layer).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            offenders += [f"{path.name}: {n}" for n in names if n.startswith(FORBIDDEN[layer])]
    assert offenders == []

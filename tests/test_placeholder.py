"""El paquete se importa y su versión coincide con pyproject.toml (#182)."""

import re
from pathlib import Path

import Klaus_proxy_local

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def pyproject_version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(), re.MULTILINE)
    assert m, "pyproject.toml sin version"
    return m.group(1)


def test_version() -> None:
    """__version__ coincide con pyproject.toml: no hay que tocarlo en cada release."""
    assert Klaus_proxy_local.__version__ == pyproject_version()

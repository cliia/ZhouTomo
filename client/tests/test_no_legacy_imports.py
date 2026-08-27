"""Prevent reintroduction of pre-package client import names."""

from pathlib import Path
import re


LEGACY_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+"
    r"(?:agent_client|config|model|resources|src|strategy|view|autofocus|autotilt|domain)"
    r"(?:\.|\s|$)"
)


def test_client_source_uses_only_canonical_package_imports():
    package_dir = Path(__file__).resolve().parents[1] / "src" / "zhoutomo_client"
    offenders = []

    for path in sorted(package_dir.rglob("*.py")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY_IMPORT.match(line):
                offenders.append(
                    f"{path.relative_to(package_dir)}:{line_number}: {line.strip()}"
                )

    assert not offenders, "Legacy client imports remain:\n" + "\n".join(offenders)

"""AST scan enforcing AC-8 / AD-1 / AD-6 / AD-11."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "retail_agent"
CLOCK_FILE = PKG / "core" / "clock.py"
PY_FILES = sorted([*PKG.rglob("*.py"), *(ROOT / "tests").rglob("*.py")])
SRC_FILES = sorted(PKG.rglob("*.py"))


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def imported_modules(source: str, module: str, is_package: bool = False) -> list[str]:
    """Absolute names of every module imported by ``source``."""
    package = module if is_package else module.rpartition(".")[0]
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                prefix = ".".join(base)
                target = f"{prefix}.{node.module}" if node.module else prefix
                names.extend([target] if node.module else [f"{prefix}.{a.name}" for a in node.names])
            else:
                names.append(node.module or "")
    return names


WALL_CLOCK_ATTRS = {"now", "utcnow", "today"}
TIME_FUNCS = {"time", "time_ns"}


def wall_clock_calls(source: str) -> list[str]:
    """References to ``datetime.now/utcnow/today``, ``date.today`` and ``time.time``.

    Import aliases are resolved, and a bare reference counts as well as a call,
    so ``n = datetime.now`` and ``from time import time`` are caught too.
    """
    tree = ast.parse(source)
    module_names = {"datetime"}  # names bound to the datetime module
    class_names = {"datetime", "date"}  # names bound to datetime.datetime / datetime.date
    time_names = {"time"}  # names bound to the time module
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "datetime":
                    module_names.add(a.asname or a.name)
                elif a.name == "time":
                    time_names.add(a.asname or a.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "datetime":
            class_names.update(a.asname or a.name for a in node.names if a.name in {"datetime", "date"})
        elif isinstance(node, ast.ImportFrom) and node.module == "time":
            found.extend(f"time.{a.name}" for a in node.names if a.name in TIME_FUNCS)

    def is_clock_class(value: ast.expr) -> bool:
        if isinstance(value, ast.Name):
            return value.id in class_names
        return (
            isinstance(value, ast.Attribute)
            and value.attr in {"datetime", "date"}
            and isinstance(value.value, ast.Name)
            and value.value.id in module_names
        )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr in WALL_CLOCK_ATTRS and is_clock_class(node.value):
            found.append(f"{ast.unparse(node.value)}.{node.attr}")
        elif (
            node.attr in TIME_FUNCS
            and isinstance(node.value, ast.Name)
            and node.value.id in time_names
        ):
            found.append(f"{node.value.id}.{node.attr}")
    return found


def _imports_of(path: Path) -> list[str]:
    return imported_modules(
        path.read_text(encoding="utf-8"), _module_name(path), path.name == "__init__.py"
    )


def _layer_files(layer: str) -> list[Path]:
    return [p for p in SRC_FILES if p.relative_to(PKG).parts[0] == layer]


# --- The three AC-8 rules -------------------------------------------------


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_wall_clock_outside_core_clock(path):
    if path == CLOCK_FILE:
        return
    assert wall_clock_calls(path.read_text(encoding="utf-8")) == []


def test_api_does_not_import_repositories():
    offenders = {
        str(p.relative_to(ROOT)): m
        for p in _layer_files("api")
        for m in _imports_of(p)
        if m.startswith("src.retail_agent.repositories")
    }
    assert offenders == {}


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_retail_agent_import_without_src_prefix(path):
    bad = [m for m in _imports_of(path) if m == "retail_agent" or m.startswith("retail_agent.")]
    assert bad == []


# --- Further AD-1 / AD-11 rules -------------------------------------------


def test_services_and_domain_do_not_import_web_framework():
    offenders = [
        (str(p.relative_to(ROOT)), m)
        for layer in ("services", "domain")
        for p in _layer_files(layer)
        for m in _imports_of(p)
        if m.split(".")[0] in {"fastapi", "starlette"}
    ]
    assert offenders == []


def test_domain_imports_only_stdlib_pydantic_and_domain():
    allowed_roots = set(sys.stdlib_module_names) | {"pydantic", "__future__"}
    offenders = [
        (str(p.relative_to(ROOT)), m)
        for p in _layer_files("domain")
        for m in _imports_of(p)
        if not (m.startswith("src.retail_agent.domain") or m.split(".")[0] in allowed_roots)
    ]
    assert offenders == []


def test_package_uses_relative_imports_internally():
    offenders = []
    for p in SRC_FILES:
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").startswith("src"):
                offenders.append(str(p.relative_to(ROOT)))
            if isinstance(node, ast.Import) and any(a.name.startswith("src") for a in node.names):
                offenders.append(str(p.relative_to(ROOT)))
    assert offenders == []


# --- The scanner itself must catch violations ----------------------------


@pytest.mark.parametrize(
    "src",
    [
        "from datetime import datetime\ndatetime.now()",
        "import datetime\ndatetime.datetime.utcnow()",
        "from datetime import date\ndate.today()",
        # Bypasses found in review: aliases, datetime.today, time.time, bare references.
        "from datetime import datetime as dt\ndt.now()",
        "from datetime import date as D\nD.today()",
        "import datetime as dtm\ndtm.datetime.now()",
        "import datetime as dtm\ndtm.date.today()",
        "from datetime import datetime\ndatetime.today()",
        "import time\ntime.time()",
        "import time as t\nt.time_ns()",
        "from time import time\ntime()",
        "from datetime import datetime\nnow = datetime.now\nnow()",
    ],
)
def test_scanner_detects_wall_clock(src):
    assert wall_clock_calls(src)


def test_scanner_ignores_injected_clock():
    assert wall_clock_calls("clock.now()\nclock.today()") == []


def test_scanner_ignores_non_clock_attributes():
    src = "import datetime\nfrom datetime import date\ndatetime.date(2026, 1, 1)\ndate.fromisoformat('x')\nself.time"
    assert wall_clock_calls(src) == []


def test_scanner_resolves_relative_imports():
    mods = imported_modules(
        "from ..repositories.order_repository import X\nfrom . import deps\nimport retail_agent.x",
        "src.retail_agent.api.orders",
    )
    assert mods == [
        "src.retail_agent.repositories.order_repository",
        "src.retail_agent.api.deps",
        "retail_agent.x",
    ]

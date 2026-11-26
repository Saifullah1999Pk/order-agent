"""Layer boundary tests (contracts/boundaries.md).

Assumes the project is installed in the venv (``uv run`` does an editable install),
which the later ``python -I`` subprocess tests rely on.
"""
from pathlib import Path

import pytest

from architecture import LAYERS, imported_modules, violations

ROOT = Path(__file__).resolve().parent.parent / "order_agent"

# Flat modules that exist today and are moved into layers by later steps.
LEGACY_FLAT = {
    "brief", "matching", "rules", "report", "prompt", "call",
    "llm_factory", "eval_config", "eval_llm", "suite", "throttle", "preflight",
}


def _layer_files():
    for layer in LAYERS:
        base = ROOT / layer
        if base.is_dir():
            for path in sorted(base.rglob("*.py")):
                yield pytest.param(layer, path, id=str(path.relative_to(ROOT)).replace("\\", "/"))


def test_imported_modules_resolves_relative_and_lazy_imports():
    src = "def f():\n    from . import x\nimport a.b\nfrom c import d"
    assert imported_modules(src, "order_agent.model") == {
        "order_agent.model", "order_agent.model.x", "a.b", "c", "c.d",
    }


@pytest.mark.parametrize(
    "src",
    [
        "import pipecat",
        "def f():\n    import google.genai",
        "from order_agent.controller import x",
        "from pipecat.services.google.llm import X",
        "import loguru",
        "import requests",
        "from order_agent import config",
    ],
)
def test_checker_catches_forbidden_model_imports(src):
    assert violations(src, "model") != []


def test_checker_catches_relative_import_resolving_outside_layer():
    assert violations("from . import x", "model", package="order_agent") != []
    assert violations("from .. import controller", "model", package="order_agent.model") != []


def test_checker_accepts_clean_model_snippet():
    src = (
        "import re\nfrom decimal import Decimal\nimport yaml\nfrom pydantic import BaseModel\n"
        "from order_agent.model.brief import OrderBrief\nfrom . import brief\nfrom __future__ import annotations\n"
    )
    assert violations(src, "model") == []


@pytest.mark.parametrize("layer,path", list(_layer_files()))
def test_real_tree_has_no_violations(layer, path):
    package = ".".join(("order_agent",) + path.relative_to(ROOT).parts[:-1])
    assert violations(path.read_text(encoding="utf-8"), layer, package=package) == []


def test_every_module_is_classified():
    unclassified = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if len(rel.parts) > 1 or rel.name in ("__init__.py", "config.py"):
            continue
        if rel.stem not in LEGACY_FLAT:
            unclassified.append(str(rel))
    assert unclassified == []


@pytest.mark.parametrize(
    "src",
    [
        "import pipecat",
        "from fastapi import FastAPI",
        "from order_agent.heads.voice import x",
        "from order_agent.config import Settings",
        "from order_agent.evaltools import x",
    ],
)
def test_checker_catches_forbidden_controller_imports(src):
    assert violations(src, "controller") != []


def test_checker_accepts_clean_controller_snippet():
    src = "from loguru import logger\nfrom order_agent.model.brief import OrderBrief\n"
    assert violations(src, "controller") == []


@pytest.mark.parametrize(
    "src",
    [
        "from fastapi import FastAPI",
        "from order_agent.heads.http_api import x",
        "from order_agent.evaltools import x",
        "from order_agent.model.rules import OrderSession",
        "from order_agent.model.matching import match_line",
        "from order_agent.model import rules",
    ],
)
def test_checker_catches_forbidden_voice_head_imports(src):
    assert violations(src, "heads/voice", package="order_agent.heads.voice") != []


def test_checker_accepts_clean_voice_head_snippet():
    src = (
        "import pipecat\nfrom order_agent.controller import CallController\n"
        "from order_agent.config import Settings\nfrom order_agent.model.brief import OrderBrief\n"
    )
    assert violations(src, "heads/voice", package="order_agent.heads.voice") == []


def test_legacy_tools_module_gone():
    import order_agent.call as call

    assert not (ROOT / "tools.py").exists()
    assert not hasattr(call, "make_on_end")


@pytest.mark.parametrize(
    "src",
    [
        "from order_agent.controller import x",
        "from order_agent.heads.voice import x",
    ],
)
def test_checker_catches_forbidden_evaltools_imports(src):
    assert violations(src, "evaltools", package="order_agent.evaltools") != []


def test_checker_accepts_clean_evaltools_snippet():
    src = "import pipecat\nimport yaml\nfrom order_agent.model.report import CallReport\n"
    assert violations(src, "evaltools", package="order_agent.evaltools") == []

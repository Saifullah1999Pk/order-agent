"""Layer boundary tests (contracts/boundaries.md).

Assumes the project is installed in the venv (``uv run`` does an editable install),
which the later ``python -I`` subprocess tests rely on.
"""
from pathlib import Path

import pytest

from architecture import LAYERS, _under, imported_modules, violations

ROOT = Path(__file__).resolve().parent.parent / "order_agent"

# The one allowed flat module besides __init__.py and config.py: evals/*.yaml name factories as
# order_agent.eval_llm.*, so it stays as a re-export-only compat module (FR-010, analysis F1).
COMPAT_MODULES = {"eval_llm"}


def _layer_files():
    for layer in LAYERS:
        base = ROOT / layer
        assert base.is_dir(), f"layer directory missing: {base}"
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
        if rel.stem not in COMPAT_MODULES:
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
    assert not (ROOT / "tools.py").exists()


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


REPO = ROOT.parent
LEGACY_SHIMS = ("brief", "matching", "rules", "report", "prompt", "call", "llm_factory")


def test_no_imports_of_legacy_shims():
    """T051: nothing imports order_agent.{brief,matching,rules,report,prompt,call,llm_factory}."""
    shim_paths = {ROOT / f"{name}.py" for name in LEGACY_SHIMS}
    banned = {f"order_agent.{name}" for name in LEGACY_SHIMS}
    sources = [*REPO.glob("*.py"), *ROOT.rglob("*.py"), *(REPO / "tests").glob("*.py"), *(REPO / "evals").rglob("*.py")]
    offenders = []
    for path in sorted(set(sources)):
        if path in shim_paths or path == Path(__file__):
            continue
        package = ".".join(("order_agent",) + path.relative_to(ROOT).parts[:-1]) if ROOT in path.parents else ""
        for name in imported_modules(path.read_text(encoding="utf-8"), package):
            if any(_under(name, b) for b in banned):
                offenders.append(f"{path.relative_to(REPO)}: {name}")
    assert offenders == []


def test_layer_directories_exist():
    for layer in LAYERS:
        assert (ROOT / layer).is_dir(), layer


def test_compat_eval_llm_is_reexports_only():
    import ast

    tree = ast.parse((ROOT / "eval_llm.py").read_text(encoding="utf-8"))
    names = None
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # module docstring
        if isinstance(node, ast.ImportFrom):
            assert node.module == "order_agent.evaltools.eval_llm"
        elif isinstance(node, ast.Assign) and [t.id for t in node.targets] == ["__all__"]:
            names = [e.value for e in node.value.elts]
        else:
            raise AssertionError(f"compat module may only re-export, found {type(node).__name__}")
    imported = {a.name for n in tree.body if isinstance(n, ast.ImportFrom) for a in n.names}
    assert names is not None and set(names) == imported
    assert set(names) == {
        "gemini_llm", "gemini_classifier", "gemini_native_llm", "groq_llm", "groq_classifier",
        "ollama_classifier", "ThrottledOpenAILLMService", "ThrottledGroqLLMService",
    }


def test_runtime_import_graph():
    """contracts/boundaries.md item 4: importing Model and Controller loads no speech or web stack."""
    import json
    import subprocess
    import sys

    code = (
        "import sys, json, pkgutil\n"
        "import order_agent.model, order_agent.controller\n"
        "import importlib\n"
        "for pkg in (order_agent.model, order_agent.controller):\n"
        "    for m in pkgutil.iter_modules(pkg.__path__):\n"
        "        importlib.import_module(pkg.__name__ + '.' + m.name)\n"
        "banned = ('pipecat', 'fastapi', 'starlette', 'uvicorn', 'google', 'openai', 'torch')\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.split('.')[0] in banned)))\n"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []

import tomllib
from pathlib import Path


def test_http_stack_imports():
    from fastapi.testclient import TestClient  # noqa: F401
    import uvicorn  # noqa: F401


def test_pyproject_declares_fastapi_and_uvicorn():
    data = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
    deps = " ".join(data["project"]["dependencies"])
    assert "fastapi" in deps
    assert "uvicorn" in deps

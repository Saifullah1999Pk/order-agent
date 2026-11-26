"""The README's architecture section must stay in step with the code tree (FR-011, SC-006)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
LAYER_DIRS = [
    "order_agent/model",
    "order_agent/controller",
    "order_agent/evaltools",
] + sorted(  # every head directory, so a new head must be documented too
    p.relative_to(ROOT).as_posix() for p in (ROOT / "order_agent" / "heads").iterdir()
    if p.is_dir() and p.name != "__pycache__"
)


def test_readme_has_architecture_headings():
    assert "## Architecture" in README
    assert "Add a new head" in README


def test_readme_mentions_each_layer_directory():
    for layer in LAYER_DIRS:
        assert layer in README, layer


def test_readme_module_map_names_every_module():
    missing = []
    for layer in LAYER_DIRS:
        for path in sorted((ROOT / layer).rglob("*.py")):
            if path.name == "__init__.py":
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel not in README:
                missing.append(rel)
    assert not missing, f"README module map lacks: {missing}"


def test_readme_documents_run_command_dependency_rule_and_boundary_test():
    assert "uv run python -m order_agent.heads.http_api" in README
    assert "tests/test_architecture.py" in README
    assert "heads -> controller -> model" in README


def test_readme_layout_block_matches_the_new_tree():
    assert "  rules.py             the rules engine" not in README
    assert "  call.py              call state" not in README
    assert "order_agent/rules.py" not in README  # the engine lives in order_agent/model/rules.py


def test_readme_unit_test_count_matches_collection():
    import re
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    count = int(re.search(r"(\d+) tests? collected", out).group(1))
    assert f"| Unit tests | {count} passing |" in README

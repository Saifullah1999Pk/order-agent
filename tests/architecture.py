"""Import-boundary checker used by test_architecture.py. Stdlib only."""
import ast
import sys

_THIRD_PARTY_BANNED = (
    "pipecat", "google", "openai", "groq", "ollama", "anthropic", "fastapi", "starlette",
    "uvicorn", "aiohttp", "httpx", "requests", "websockets", "loguru", "dotenv",
)

# SC-005: no head reaches the rules engine or matching except through the Controller.
_HEAD_NARROWING = ("order_agent.model.rules", "order_agent.model.matching")

LAYERS = {
    "model": {
        "third_party": {"pydantic", "yaml"},
        "internal": ("order_agent.model",),
        "forbidden": _THIRD_PARTY_BANNED
        + ("order_agent.controller", "order_agent.heads", "order_agent.evaltools", "order_agent.config"),
    },
    "controller": {
        "third_party": {"loguru"},
        "internal": ("order_agent.model", "order_agent.controller"),
        "forbidden": tuple(m for m in _THIRD_PARTY_BANNED if m != "loguru")
        + ("order_agent.heads", "order_agent.evaltools", "order_agent.config"),
    },
    "heads/voice": {
        "third_party": {"pipecat", "google", "loguru", "dotenv"},
        "internal": ("order_agent.model", "order_agent.controller", "order_agent.config", "order_agent.heads.voice"),
        "forbidden": ("fastapi", "starlette", "uvicorn", "order_agent.heads.http_api", "order_agent.evaltools")
        + _HEAD_NARROWING,
    },
    "evaltools": {
        # Eval tooling may use any third-party library; it must not reach the Controller or a head.
        "third_party": None,
        "internal": ("order_agent.model", "order_agent.config", "order_agent.evaltools"),
        "forbidden": ("order_agent.controller", "order_agent.heads"),
    },
    "heads/http_api": {
        "third_party": {"fastapi", "starlette", "uvicorn", "pydantic", "loguru"},
        "internal": ("order_agent.model", "order_agent.controller", "order_agent.config", "order_agent.heads.http_api"),
        "forbidden": ("pipecat", "torch", "faster_whisper", "kokoro", "google", "openai", "groq", "ollama",
                      "order_agent.heads.voice", "order_agent.evaltools")
        + _HEAD_NARROWING,
    },
}


def imported_modules(source: str, package: str) -> set[str]:
    """Dotted names imported anywhere in ``source`` (any depth); relative imports are
    resolved against ``package``. ``from m import n`` yields both ``m`` and ``m.n``."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - (node.level - 1)])
                module = f"{base}.{node.module}" if node.module else base
            else:
                module = node.module or ""
            found.add(module)
            found.update(f"{module}.{a.name}" for a in node.names if a.name != "*")
    return found


def _under(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def violations(source: str, layer: str, package: str | None = None) -> list[str]:
    rule = LAYERS[layer]
    package = package or "order_agent." + layer.replace("/", ".")
    bad = []
    for name in sorted(imported_modules(source, package)):
        top = name.split(".")[0]
        if any(_under(name, p) for p in rule["forbidden"]):
            bad.append(name)
        elif top == "order_agent":
            if name != "order_agent" and not any(_under(name, p) for p in rule["internal"]):
                bad.append(name)
        elif (top not in sys.stdlib_module_names and rule["third_party"] is not None
              and top not in rule["third_party"]):
            bad.append(name)
    return bad

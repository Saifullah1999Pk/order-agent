"""Run the HTTP head locally: ``uv run python -m order_agent.heads.http_api [--port N]``."""

import argparse
from collections.abc import Callable, Sequence

from order_agent.config import load_settings
from order_agent.heads.http_api.app import create_app

HOST = "127.0.0.1"  # local only: no authentication, so no --host option


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="order_agent.heads.http_api", description=__doc__)
    parser.set_defaults(host=HOST)
    parser.add_argument("--port", type=int, default=8000, help="port to listen on (default 8000)")
    return parser


def main(argv: Sequence[str] | None = None, serve: Callable | None = None) -> None:
    args = build_parser().parse_args(argv)
    app = create_app(load_settings().reports_dir)
    if serve is None:
        import uvicorn

        serve = uvicorn.run
    serve(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

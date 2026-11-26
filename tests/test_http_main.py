from pathlib import Path

from order_agent.heads.http_api.__main__ import build_parser, main


def test_defaults_are_local_port_8000():
    args = build_parser().parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_no_host_option():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["--host", "0.0.0.0"])


def test_main_serves_on_loopback_with_port(monkeypatch, tmp_path):
    monkeypatch.setenv("ORDER_REPORTS_DIR", str(tmp_path / "r"))
    calls = []

    def fake(app, **kwargs):
        calls.append((app, kwargs))

    main(["--port", "9001"], serve=fake)
    (app, kwargs), = calls
    assert kwargs == {"host": "127.0.0.1", "port": 9001}
    assert app.state.reports_dir == Path(tmp_path / "r")
    assert app.title

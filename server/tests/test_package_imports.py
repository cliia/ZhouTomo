from pathlib import Path

from zhoutomo_server.api import create_app
from zhoutomo_server.drivers import temscript
from zhoutomo_server.main import AgentConfig, parse_arguments
from zhoutomo_server.wiring import create_null_wiring


def test_server_package_imports_without_hardware():
    app = create_app()
    assert app.title == "ZhouTomo API Server"
    assert temscript.NullMicroscope is not None
    assert create_null_wiring().mode == "null"


def test_server_src_root_has_no_legacy_python_modules():
    src_root = Path(__file__).resolve().parents[1] / "src"
    assert list(src_root.glob("*.py")) == []


def test_cli_default_port_and_explicit_override(monkeypatch):
    monkeypatch.delenv("AGENT_PORT", raising=False)
    assert parse_arguments(["--mode", "null"]).port == 9000
    assert parse_arguments(["--mode", "null", "--port", "9100"]).port == 9100

    config = AgentConfig()
    assert config.port == 9000

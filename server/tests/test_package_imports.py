from zhoutomo_server.api import create_app
from zhoutomo_server.drivers import temscript


def test_server_package_facades_import_without_hardware():
    app = create_app()
    assert app.title == "ZhouTomo API Server"
    assert temscript is not None

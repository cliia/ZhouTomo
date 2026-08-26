from zhoutomo_protocol import MicroscopeParams
from zhoutomo_server.domain import validate_params


def test_projection_magnification_validation():
    params = MicroscopeParams()
    params.projection.magnification = params.projection.max_magnification + 1

    assert validate_params(params)

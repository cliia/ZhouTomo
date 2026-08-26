from zhoutomo_protocol import StagePosition


def test_client_can_import_shared_protocol():
    assert StagePosition(a=0.5).a == 0.5

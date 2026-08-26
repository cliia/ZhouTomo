from zhoutomo_protocol import StagePosition, create_default_state, state_to_dict


def test_state_serialization_preserves_stage_units_and_values():
    state = create_default_state()
    state.stage.position = StagePosition(x=1e-6, y=2e-6, z=3e-6, a=0.1, b=-0.2)

    payload = state_to_dict(state)

    assert payload["stage"]["position"] == {
        "x": 1e-6,
        "y": 2e-6,
        "z": 3e-6,
        "a": 0.1,
        "b": -0.2,
    }

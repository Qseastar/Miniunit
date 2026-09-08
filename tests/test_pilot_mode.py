from introai_tutor.pilot_mode import is_pilot_mode_enabled


def test_pilot_mode_is_default_off_and_accepts_explicit_opt_in_values():
    assert is_pilot_mode_enabled("") is False
    assert is_pilot_mode_enabled("0") is False
    assert is_pilot_mode_enabled("false") is False
    assert is_pilot_mode_enabled("off") is False
    assert is_pilot_mode_enabled("no") is False
    assert is_pilot_mode_enabled("unexpected") is False
    assert is_pilot_mode_enabled("1") is True
    assert is_pilot_mode_enabled("true") is True
    assert is_pilot_mode_enabled("on") is True
    assert is_pilot_mode_enabled("yes") is True

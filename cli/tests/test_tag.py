import pytest
from llc.tag import _parse_tag, _compute_bump


class TestParseTag:
    def test_parses_full_semver(self):
        assert _parse_tag("v1.2.3") == (1, 2, 3, None)

    def test_parses_with_rc(self):
        assert _parse_tag("v1.2.3-rc.4") == (1, 2, 3, 4)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_tag("abc")


class TestComputeBump:
    def test_major_bump(self):
        assert _compute_bump((1, 2, 3, None), "major") == "v2.0.0"

    def test_minor_bump(self):
        assert _compute_bump((1, 2, 3, None), "minor") == "v1.3.0"

    def test_patch_bump(self):
        assert _compute_bump((1, 2, 3, None), "patch") == "v1.2.4"

import pytest

from scriptmatria import gematria


@pytest.mark.parametrize("phrase,expected", [
    # Hand-checked: a=1 ... z=26 / a=26 ... z=1, reductions digit-summed.
    ("abc", {"EO": 6, "FR": 6, "RO": 75, "RR": 21, "CH": 6}),
    ("z", {"EO": 26, "FR": 8, "RO": 1, "RR": 1, "CH": 7}),
    ("Lakers", {"EO": 66, "FR": 21, "RO": 96, "RR": 42, "CH": 16}),
])
def test_known_values(phrase, expected):
    assert gematria.all_values(phrase) == expected


def test_normalization_ignores_case_spaces_digits_and_punctuation():
    assert gematria.all_values("New-York 76ers!") == gematria.all_values("newyorkers")


def test_reduction_tables_are_single_digit():
    for code in ("FR", "RR"):
        assert set(gematria.CIPHERS[code][1].values()) <= set(range(1, 10))
    assert gematria.FULL_REDUCTION["k"] == 2 and gematria.FULL_REDUCTION["v"] == 4
    assert gematria.REVERSE_REDUCTION["a"] == 8

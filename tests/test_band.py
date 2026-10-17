import pytest

from pr_triage.domain.band import Band, determine_band


@pytest.mark.parametrize(
    "value, expected",
    [
        (1, Band.NO_BLOCKERS),
        (999.99, Band.NO_BLOCKERS),
        (1000, Band.POLICY_TO_BE_VERIFIED),
        (5000, Band.POLICY_TO_BE_VERIFIED),
        (5000.01, Band.HUMAN_ACTION),
        (100000, Band.HUMAN_ACTION),
    ],
)
def test_band_boundaries(value, expected):
    assert determine_band(value) == expected
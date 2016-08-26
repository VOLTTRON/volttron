import pytest


def skip_if_not_encrypted(encrypted):
    if not encrypted:
        pytest.skip("Only encrypted available for this test")
import pytest
from volttron.platform.agent.utils import is_valid_identity


@pytest.mark.agent
def test_none_returns_false():
    assert not is_valid_identity(None)


@pytest.mark.agent
def test_valid_identity_returns_true():
    assert is_valid_identity('valid.idenitty_here-orthere')


@pytest.mark.agent
def test_invalid_idenity_returns_false():
    assert not is_valid_identity("#Foo")
    assert not is_valid_identity(" Foo")
    assert not is_valid_identity("Foo+")
    assert not is_valid_identity("Foo?")


import pytest

from volttrontesting.fixtures.volttron_platform_fixtures import cleanup_wrappers
from volttrontesting.utils.platformwrapper import PlatformWrapper


@pytest.mark.wrapper
def test_fixture_returns_correct_number_of_instances(get_volttron_instances):

    num_instances = 5
    wrappers = get_volttron_instances(num_instances, False)

    assert num_instances == len(wrappers)
    for w in wrappers:
        assert isinstance(w, PlatformWrapper)
        assert not w.is_running()


@pytest.mark.wrapper
def test_fixture_starts_platforms(get_volttron_instances):
    num_instances = 5
    wrappers = get_volttron_instances(num_instances)

    assert num_instances == len(wrappers)
    for w in wrappers:
        assert isinstance(w, PlatformWrapper)
        assert w.is_running()
        w.shutdown_platform()

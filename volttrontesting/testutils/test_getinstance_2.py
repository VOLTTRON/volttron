import pytest

from volttrontesting.utils.platformwrapper import PlatformWrapper


@pytest.mark.wrapper
def test_fixture_starts_platforms(get_volttron_instances):
    num_instances = 5
    wrappers = get_volttron_instances(num_instances)

    assert num_instances == len(wrappers)
    for w in wrappers:
        assert isinstance(w, PlatformWrapper)
        assert w.is_running()
        w.shutdown_platform()

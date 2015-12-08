import pytest

def test_volttron_fixtures(volttron_instance_1, volttron_instance_2):
    assert volttron_instance_1 is not None
    assert volttron_instance_2 is not None
    assert volttron_instance_1 != volttron_instance_2

def test_instance_enviornment(volttron_instance_1, volttron_instance_2):
    assert volttron_instance_1.env['VOLTTRON_HOME'] != \
        volttron_instance_2.env['VOLTTRON_HOME']

def test_platform_startup(volttron_instance_1, volttron_instance_2):
    assert volttron_instance_1.is_running()
    assert volttron_instance_2.is_running()
    assert not volttron_instance_1.twistd_is_running()
    assert not volttron_instance_2.twistd_is_running()

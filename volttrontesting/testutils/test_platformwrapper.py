import pytest

def test_volttron_fixtures(volttron_instance_1, volttron_instance_2):
    assert volttron_instance_1 is not None
    assert volttron_instance_2 is not None
    assert volttron_instance_1 != volttron_instance_2
    
def test_instance_enviornment(volttron_instance_1, volttron_instance_2):
    assert volttron_instance_1.env['VOLTTRON_HOME'] != \
        volttron_instance_2.env['VOLTTRON_HOME']

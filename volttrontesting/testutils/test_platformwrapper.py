import pytest

def test_volttron_fixtures(volttron_instance_1, volttron_instance_2):
    assert volttron_instance_1 is not None
    assert volttron_instance_2 is not None
    assert len(volttron_instance_1['result']) > 0
    assert len(volttron_instance_2['result']) > 0

"""actuator_control is never granted when an agent is installed.

An operator grants it by hand, agent by agent. These tests run the install-time authorization against a fake
AuthFile and read the entry it would write.
"""
from unittest.mock import MagicMock, patch

import pytest

from volttron.platform.agent.known_identities import (ACTUATOR_CONTROL, VOLTTRON_CENTRAL,
                                                      VOLTTRON_CENTRAL_PLATFORM)
from volttron.platform.aip import AIPplatform


@pytest.mark.parametrize("identity", ['my.control.agent', 'platform.actuator', VOLTTRON_CENTRAL,
                                      VOLTTRON_CENTRAL_PLATFORM])
def test_install_time_entry_has_no_actuator_control(identity):
    with patch('volttron.platform.aip.AuthFile') as auth_file:
        AIPplatform._authorize_agent_keys(MagicMock(), 'uuid', identity, 'public-key')
    auth_file.return_value.add.assert_called_once()
    entry = auth_file.return_value.add.call_args[0][0]
    assert entry.user_id == identity
    assert 'edit_config_store' in entry.capabilities
    assert ACTUATOR_CONTROL not in entry.capabilities

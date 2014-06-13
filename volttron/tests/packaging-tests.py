import unittest
import os
import shutil
import sys

from collections import namedtuple

from volttron.platform.packaging import AgentPackage
from volttron.platform.packaging import AgentPackageError

# Temporary path for working during running of package/unpackage tests.
TMP_AGENT_DIR = '/tmp/agent-dir'

class TestPackaging(unittest.TestCase):

    
    def setUp(self):
        '''
        Recreates the temporary agent directory before each run
        '''
        if os.path.exists(TMP_AGENT_DIR):
            shutil.rmtree(TMP_AGENT_DIR)
        os.makedirs(TMP_AGENT_DIR)

    def test_can_create_an_initial_package(self):
        '''
        
        '''
    
    
    def test_raises_package_error_if_invalid_settings_passed(self):
        '''
        This test passes under the following conditions:
            1. The settings object has an angent-dir setting
            2. The agent-dir exists
            3. An AgentPackageError is thrown if agent-dir doesn't exist
            4. An AgentPackageError is thrown if the settings object doesn't
               include an agent-dir element.
        '''
        # TODO allow global_settings to be validated here as well.
        self.assertRaises(AgentPackageError, lambda: AgentPackage())
        sys.exc_clear()
        self.assertRaises(AgentPackageError, lambda: AgentPackage())
        sys.exc_clear()

        # agent_dir not specified on the namedtuple
        BadSettings = namedtuple('BadSettings', ['not_agent_dir'])
        badsettings = BadSettings(not_agent_dir = '50')  
        print(badsettings.not_agent_dir)     
        self.assertRaises(AgentPackageError, lambda: AgentPackage(badsettings))
  

        # invalid agent_dir specified
        Settings = namedtuple('Settings', ['agent_dir'])
        invalid_dir = Settings(agent_dir='/tmp/garbage')
        self.assertRaises(AgentPackageError, lambda: AgentPackage(invalid_dir))

        # Shouldn't throw an error
        valid_settings = Settings(agent_dir=TMP_AGENT_DIR)



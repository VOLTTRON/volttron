import json
import os
import shutil
import subprocess
import sys
import time
import tempfile
import unittest

from contextlib import closing
from StringIO import StringIO

import zmq

from volttron.platform import aip
from volttron.platform.control import server
from volttron.platform import packaging
from volttron.tests.platform_wrapper import PlatformWrapper

try:
    from volttron.restricted import (auth, certs)
except ImportError:
    auth = None
    certs = None

#Filenames for the config files which are created during setup and then
#passed on the command line
TMP_PLATFORM_CONFIG_FILENAME = "test-config.ini"
TMP_SMAP_CONFIG_FILENAME = "test-smap.ini"

#Used to fill in TWISTED_CONFIG template
TEST_CONFIG_FILE = 'base-platform-test.json'

PLATFORM_CONFIG_UNRESTRICTED = """
no-resource-monitor
no-verify
no-mobility

control-socket = {tmpdir}/run/control
"""


PLATFORM_CONFIG_RESTRICTED = """
mobility-address = {mobility-address}
"""



TWISTED_CONFIG = """
[report 0]
ReportDeliveryLocation = {smap-uri}/add/{smap-key}

[/]
type = Collection
Metadata/SourceName = {smap-source}
uuid = {smap-uuid}

[/datalogger]
type = volttron.drivers.data_logger.DataLogger
interval = 1

"""

UNRESTRICTED = 0
VERIFY_ONLY = 1
RESOURCE_CHECK_ONLY = 2
RESTRICTED = 3

MODES = (UNRESTRICTED, VERIFY_ONLY, RESOURCE_CHECK_ONLY, RESTRICTED)

rel_path = './'

VSTART = os.path.join(rel_path, "env/bin/volttron")
VCTRL = os.path.join(rel_path, "env/bin/volttron-ctl")

PUBLISH_ADDRESS = 'ipc:///tmp/volttron-platform-agent-publish'
SUBSCRIBE_ADDRESS = 'ipc:///tmp/volttron-platform-agent-subscribe'


class BasePlatformTest(unittest.TestCase):

    cleanup_tempdir = True

    def env(self):
        return self.platform_wrapper.env

    def setUp(self):
        self.platform_wrapper = PlatformWrapper()

    def startup_platform(self, platform_config, volttron_home=None,
                         use_twistd=True, mode=UNRESTRICTED):

        if volttron_home != None:
            self.platform_wrapper.initialize_volttron_home(volttron_home)
        self.platform_wrapper.startup_platform(platform_config,
                                               use_twistd=use_twistd,
                                               mode=mode)

    def fillout_file(self, filename, template, config_file):
        return self.platform_wrapper.fillout_file(filename, template, config_file)

    def build_agentpackage(self, distdir):
        pwd = os.getcwd()
        try:
            basepackage = os.path.join(self.tmpdir,distdir)
            shutil.copytree(os.path.abspath(distdir), basepackage)

            os.chdir(basepackage)
            sys.argv = ['', 'bdist_wheel']
            exec(compile(open('setup.py').read(), 'setup.py', 'exec'))

            wheel_name = os.listdir('./dist')[0]

            wheel_file_and_path = os.path.join(os.path.abspath('./dist'), wheel_name)
        finally:
            os.chdir(pwd)

        return wheel_file_and_path

    def direct_build_agentpackage(self, agent_dir):
        uuid = self.platform_wrapper.direct_build_agentpackage(agent_dir)
        self.assertTrue(uuid, "Invalid uuid returned")
        return uuid

    def direct_configure_agentpackage(self, agent_wheel, config_file):
        packaging.add_files_to_package(agent_wheel, {'config_file':os.path.join(rel_path, config_file)})

    def direct_buid_install_agent(self, agent_dir, config_file):
        uuid = self.platform_wrapper.direct_build_agentpackage(agent_dir,
                                                               config_file)
        self.assertTrue(uuid, "Invalid uuid returned")
        return uuid


    def direct_remove_agent(self, uuid):
        uuid = self.direct_remove_agent(uuid)
        self.assertTrue(uuid, "Invalid uuid returned")
        return uuid

    def direct_build_install_run_agent(self, agent_dir, config_file):
        uuid = self.platform_wrapper.direct_build_install_run_agent(agent_dir,
                                                                    config_file)
        self.assertTrue(uuid, "Invalid uuid returned")
        return uuid

    def direct_start_agent(self, agent_uuid):
        self.platform_wrapper.direct_start_agent(agent_uuid)

    def direct_stop_agent(self, agent_uuid):
        self.platform_wrapper.direct_stop_agent(agent_uuid)

    def check_default_dir(self, dir_to_check):
        self.platform_wrapper.check_default_dir(dir_to_check)

    def shutdown_platform(self):
        '''Stop platform here'''
        self.platform_wrapper.shutdown_platform(self.cleanup_tempdir)

    def tearDown(self):
        self.platform_wrapper.shutdown_platform(self.cleanup_tempdir)

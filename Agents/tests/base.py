import json
import os
import shutil
import subprocess
import sys
import time
import tempfile
import unittest

from contextlib import closing

from volttron.platform.control import (CTL_STATUS,
                                       CTL_INSTALL,
                                       CTL_STATUS,
                                       CTL_START,
                                       CTL_STOP)

#All paths relative to proj-dir/volttron
VSTART = "env/bin/volttron"
VCTRL = "env/bin/volttron-ctl"
# INST_EXEC = "install"
# REM_EXEC = "remove-executable"
# LOAD_AGENT = "load-agent"
# UNLOAD_AGENT = "unload-agent"
# LIST_AGENTS = "list-agents"
# STOP_AGENT = "stop-agent"
# START_AGENT = "start-agent"
# BUILD_AGENT = "volttron/scripts/build-agent.sh"
CONFIG_FILE = "test-config.ini"
SMAP_FILE = "test-smap.ini"
TEST_CONFIG_FILE = 'base-platform-test.json'
SMAP_KEY_FILE = 'test-smap-key.ini'
SMAP_UUID_FILE = 'test-smap-uuid.ini'

PLATFORM_CONFIG = """
[agent-exchange]
append-pid = false

[agent-paths]
config-dir = config
agents-dir = {tmpdir}/Agents
autostart-dir = {tmpdir}/autostart
bin-dir = {tmpdir}/bin
run-dir = {tmpdir}/tmp

"""

TWISTED_CONFIG = """
[report 0]
ReportDeliveryLocation = {smap-uri}

[/]
type = Collection
Metadata/SourceName = {smap-source}
uuid = {smap-uuid}

[/datalogger]
type = volttron.drivers.data_logger.DataLogger
interval = 1

"""

rel_path = '../../'


class BasePlatformTest(unittest.TestCase):

    def setUp(self):
        self.originaldir = os.getcwd()
        os.chdir(rel_path) 
    
    def startup_platform(self, platform_config):
        try:
            config = json.loads(open(platform_config, 'r').read())
        except Exception as e:
            sys.stderr.write (str(e))
            self.fail("Could not load configuration file for tests")
        self.tmpdir = tempfile.mkdtemp()
        config['tmpdir'] = self.tmpdir
        
        pconfig = os.path.join(self.tmpdir, CONFIG_FILE)
        with closing(open(pconfig, 'w')) as cfg:
            cfg.write(PLATFORM_CONFIG.format(**config))

        tconfig = os.path.join(self.tmpdir, SMAP_FILE)
        with closing(open(tconfig, 'w')) as cfg:
            cfg.write(TWISTED_CONFIG.format(**config))

        lfile = os.path.join(self.tmpdir, "volttron.log")

        self.p_process = subprocess.Popen([VSTART, "-c", pconfig, "-v", "-l", lfile])
        self.t_process = subprocess.Popen(["twistd", "-n", "smap", tconfig])
        #self.t_process = subprocess.Popen(["twistd", "-n", "smap", "test-smap.ini"])


    def build_agentpackage(self, distdir):
        pwd = os.getcwd()
        print (os.getcwd())
        try:
            basepackage = os.path.join(self.tmpdir,distdir)
            print(os.path.abspath(distdir))
            shutil.copytree(os.path.abspath(distdir), basepackage)
            
            os.chdir(basepackage)
            print(distdir)
            sys.argv = ['', 'bdist_wheel']
            exec(compile(open('setup.py').read(), 'setup.py', 'exec'))
    
            wheel_name = os.listdir('./dist')[0]
    
            wheel_file_and_path = os.path.join(os.path.abspath('./dist'), wheel_name)
        finally:
            os.chdir(pwd)
            
        return wheel_file_and_path

    def build_and_install_agent(self, agent_dir):
        agent_wheel = self.build_agentpackage(agent_dir)
        self.assertIsNotNone(agent_wheel,"Agent wheel was not built")
        results = subprocess.check_output([VCTRL,CTL_INSTALL,agent_wheel])
        self.assertTrue(results.startwith('Unpacking to: '))


    def shutdown_platform(self):
        '''Stop platform here'''
        if self.p_process != None:
            self.p_process.kill()
        else:
            print "NULL"

        if self.t_process != None:
            self.t_process.kill()
            self.t_process.wait()
        else:
            print "NULL"
        if self.tmpdir != None:
            shutil.rmtree(self.tmpdir, True)
    
    def tearDown(self):
        try:
            self.shutdown_platform()
        except Exception as e:
            sys.stderr.write( str(e))
        finally:
            os.chdir(self.originaldir)

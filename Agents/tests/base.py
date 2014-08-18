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

#Filenames for the config files which are created during setup and then
#passed on the command line
TMP_PLATFORM_CONFIG_FILENAME = "test-config.ini"
TMP_SMAP_CONFIG_FILENAME = "test-smap.ini"

#Used to fill in TWISTED_CONFIG template
TEST_CONFIG_FILE = 'base-platform-test.json'

PLATFORM_CONFIG_UNRESTRICTED = """
[agent-exchange]
append-pid = false

[agent-paths]
config-dir = config
agents-dir = {tmpdir}/Agents
autostart-dir = {tmpdir}/autostart
bin-dir = {tmpdir}/bin
run-dir = {tmpdir}/tmp

no-resource-monitor
no-verify-agents

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

UNRESTRICTED = 0
VERIFY_ONLY = 1
RESOURCE_CHECK_ONLY = 2
RESTRICTED = 3

MODES = (UNRESTRICTED, VERIFY_ONLY, RESOURCE_CHECK_ONLY)

rel_path = '../../'


class BasePlatformTest(unittest.TestCase):

    def setUp(self):
        self.originaldir = os.getcwd()
        os.chdir(rel_path) 
    
    def startup_platform(self, platform_config, mode=UNRESTRICTED):
        try:
            config = json.loads(open(platform_config, 'r').read())
        except Exception as e:
            sys.stderr.write (str(e))
            self.fail("Could not load configuration file for tests")
        
        self.tmpdir = tempfile.mkdtemp()
        config['tmpdir'] = self.tmpdir
        
        pconfig = os.path.join(self.tmpdir, TMP_PLATFORM_CONFIG_FILENAME)
        
        self.mode = mode
        
        self.assertIn(self.mode, MODES, 'Invalid platform mode set: '+str(mode))
        
        if self.mode == UNRESTRICTED:
            with closing(open(pconfig, 'w')) as cfg:
                cfg.write(PLATFORM_CONFIG_UNRESTRICTED.format(**config))
        else:
            self.fail("Platform mode not implemented: "+str(mode))

        tconfig = os.path.join(self.tmpdir, TMP_SMAP_CONFIG_FILENAME)
        with closing(open(tconfig, 'w')) as cfg:
            cfg.write(TWISTED_CONFIG.format(**config))

        lfile = os.path.join(self.tmpdir, "volttron.log")

        pparams = [VSTART, "-c", pconfig, "-v", "-l", lfile]
        print pparams
        self.p_process = subprocess.Popen(pparams)
        tparams = ["twistd", "-n", "smap", tconfig]
        print tparams
        self.t_process = subprocess.Popen(tparams)
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
        if self.mode == UNRESTRICTED or self.mode == RESOURCE_CHECK_ONLY:
            self.assertTrue(len(results) == 0)
        elif self.mode == RESTRICTED or self.mode == VERIFY_ONLY:    
            self.assertTrue(results.startswith('Unpacking to: '))


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

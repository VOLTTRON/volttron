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

from volttron.platform import aip
from volttron.platform.control import server
from volttron.platform import packaging

try:
    from volttron.restricted import (auth, certs)
except ImportError:
    auth = None
    certs = None
    

# from volttron.platform.control import (CTL_STATUS,
#                                        CTL_INSTALL,
#                                        CTL_STATUS,
#                                        CTL_START,
#                                        CTL_STOP)

#All paths relative to proj-dir/volttron
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
print VSTART

class BasePlatformTest(unittest.TestCase):

    def setUp(self):
        self.originaldir = os.getcwd()
#         os.chdir(rel_path) 
        self.tmpdir = tempfile.mkdtemp()
        self.wheelhouse = '/'.join((self.tmpdir, 'wheelhouse'))
        os.makedirs(self.wheelhouse)
        os.environ['VOLTTRON_HOME'] = self.tmpdir
        
        opts = type('Options', (), {'verify_agents': False, 'volttron_home': self.tmpdir})()
        self.test_aip = aip.AIPplatform(opts)
        self.test_aip.setup()
        
        
    def setup_connector(self):
        path = os.path.expandvars('$VOLTTRON_HOME/run/control')
        
        tries = 0
        max_tries = 5
        while(not os.path.exists(path) and tries < max_tries):
            time.sleep(5)
            tries += 1
            
        self.conn= server.ControlConnector(path)
    
    def startup_platform(self, platform_config, volttron_home=None, use_twistd = True, mode=UNRESTRICTED):
        
        
        
        try:
            config = json.loads(open(platform_config, 'r').read())
        except Exception as e:
            sys.stderr.write (str(e))
            self.fail("Could not load configuration file for tests", e)
        
#         self.tmpdir = tempfile.mkdtemp()
        config['tmpdir'] = self.tmpdir
        
        pconfig = os.path.join(self.tmpdir, TMP_PLATFORM_CONFIG_FILENAME)
        
        self.mode = mode
        
        self.assertIn(self.mode, MODES, 'Invalid platform mode set: '+str(mode))
        
        if self.mode == UNRESTRICTED:
            with closing(open(pconfig, 'w')) as cfg:
                cfg.write(PLATFORM_CONFIG_UNRESTRICTED.format(**config))
        elif self.mode == RESTRICTED:
            with closing(open(pconfig, 'w')) as cfg:
                cfg.write(PLATFORM_CONFIG_RESTRICTED.format(**config))
            
            
#                 self.create_certs()
        else:
            
            self.fail("Platform mode not implemented: "+str(mode))

        tconfig = os.path.join(self.tmpdir, TMP_SMAP_CONFIG_FILENAME)

        lfile = os.path.join(self.tmpdir, "volttron.log")
        if volttron_home is not None:
            mergetree(volttron_home, self.tmpdir)
        os.environ['VOLTTRON_HOME'] = self.tmpdir
        print (os.environ['VOLTTRON_HOME'])
        pparams = [VSTART, "-c", pconfig, "-vv", "-l", lfile]
        print pparams
        self.p_process = subprocess.Popen(pparams)
        
        self.setup_connector()
        if self.mode == RESTRICTED:
            self.conn.call.create_cgroups()
        
        self.use_twistd = use_twistd
        if self.use_twistd:
            with closing(open(tconfig, 'w')) as cfg:
                cfg.write(TWISTED_CONFIG.format(**config))

            tparams = ["env/bin/twistd", "-n", "smap", tconfig]
            self.t_process = subprocess.Popen(tparams)
            time.sleep(5)
        #self.t_process = subprocess.Popen(["twistd", "-n", "smap", "test-smap.ini"])

        

    def fillout_file(self, filename, template, config_file):
        
        try:
            config = json.loads(open(config_file, 'r').read())
        except Exception as e:
            sys.stderr.write (str(e))
            self.fail("Could not load configuration file for tests")
        
#         self.tmpdir = tempfile.mkdtemp()
        config['tmpdir'] = self.tmpdir
        
        outfile = os.path.join(self.tmpdir, filename)
        with closing(open(outfile, 'w')) as cfg:
            cfg.write(template.format(**config))
            
        return outfile



    def create_certs(self):
        auth.create_root_ca(self.tmpdir, ca_name)

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
        wheel_path = packaging.create_package(os.path.join(rel_path, agent_dir), self.wheelhouse)
            
        return wheel_path

    def direct_configure_agentpackage(self, agent_wheel, config_file):
        packaging.add_files_to_package(agent_wheel, {'config_file':os.path.join(rel_path, config_file)})
            


    def direct_buid_install_agent(self, agent_dir, config_file):
        agent_wheel = self.direct_build_agentpackage(agent_dir)
        self.direct_configure_agentpackage(agent_wheel, config_file)
        self.assertIsNotNone(agent_wheel,"Agent wheel was not built")
        
        uuid = self.test_aip.install_agent(agent_wheel)
        #aip volttron_home, verify_agents
        return uuid
#         conn.call.start_agent()

    def direct_remove_agent(self, uuid):
        uuid = self.test_aip.remove_agent(uuid)

    def direct_build_install_run_agent(self, agent_dir, config_file):
        agent_uuid = self.direct_buid_install_agent(agent_dir, config_file)
        self.direct_start_agent(agent_uuid)  
        return agent_uuid
            
    def direct_start_agent(self, agent_uuid):
        
        self.conn.call.start_agent(agent_uuid)
        time.sleep(3)
        
        status = self.conn.call.status_agents()
#         self.test_aip.status_agents()
        
#         status = self.conn.call.status_agents()
#         self.assertEquals(len(status[0]), 4, 'Unexpected status message')
        status_uuid = status[0][0]
        self.assertEquals(status_uuid, agent_uuid, "Agent status shows error")
        
        self.assertEquals(len(status[0][2]), 2, 'Unexpected agent status message')
        status_agent_status = status[0][2][1]
        self.assertNotIsInstance(status_agent_status, int, "Agent did not start successfully")
#         self.assertIn("running",status_agent_status, "Agent status shows error")
        print status
        
    def direct_stop_agent(self, agent_uuid):
        result = self.conn.call.stop_agent(agent_uuid)
        print result

            
    def check_default_dir(self, dir_to_check):
        default_dir = os.path.expanduser("~/.volttron/agents")
        self.assertNotIn(default_dir, dir_to_check, "Platform is using defaults")

    def shutdown_platform(self):
        '''Stop platform here'''
        if self.p_process != None:
            if self.conn is not None:
                self.conn.call.shutdown()
            time.sleep(3)
            self.p_process.kill()
        else:
            print "platform process was null"

        if self.use_twistd and self.t_process != None:
            self.t_process.kill()
            self.t_process.wait()
        elif self.use_twistd:
            print "twistd process was null"
        if self.tmpdir != None:
            shutil.rmtree(self.tmpdir, True)
    
    def tearDown(self):
        try:
            self.shutdown_platform()
        except Exception as e:
            sys.stderr.write( str(e))
        finally:
            os.chdir(self.originaldir)
            
    def do_nothing(self):
        pass


def mergetree(src, dst, symlinks=False, ignore=None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            mergetree(s, d, symlinks, ignore)
        else:
            if not os.path.exists(d) or os.stat(src).st_mtime - os.stat(dst).st_mtime > 1:
                shutil.copy2(s, d)

#     def build_install_run_agent(self, agent_dir, agent_name):
#         self.build_and_install_agent(agent_dir)
#         results = subprocess.check_output([VCTRL,CTL_START,agent_name])
#         self.assertTrue(len(results) == 0)
#         results = subprocess.check_output([VCTRL,CTL_STATUS])
#         print results
#         self.assertIn('running', results, "Agent was not started")
#         

#     def build_and_install_agent(self, agent_dir):
#         agent_wheel = self.build_agentpackage(agent_dir)
#         self.assertIsNotNone(agent_wheel,"Agent wheel was not built")
#         
#         sys.stderr = std_err = StringIO()
#         
#         results = subprocess.check_output([VCTRL,CTL_INSTALL,agent_wheel])
#         print ("results: "+results)
#         if self.mode == UNRESTRICTED or self.mode == RESOURCE_CHECK_ONLY:
#             self.assertTrue(len(results) == 0)
#             proc_out = std_err.getvalue().split(':')
#             print (proc_out)
#             self.check_default_dir(proc_out[1].strip())
#         elif self.mode == RESTRICTED or self.mode == VERIFY_ONLY:    
#             self.assertTrue(results.startswith('Unpacking to: '))

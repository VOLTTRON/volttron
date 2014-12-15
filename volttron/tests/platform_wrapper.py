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
from volttron.platform.control import client, server
from volttron.platform import packaging


RESTRICTED_AVAILABLE = False

try:
    from volttron.restricted import (auth, certs)
    RESTRICTED_AVAILABLE = True

except ImportError:
    RESTRICTED_AVAILABLE = False
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
TMP_PLATFORM_CONFIG_FILENAME = "config"
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
control-socket = {tmpdir}/run/control
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
SEND_AGENT = "send"

class PlatformWrapper():

    def __init__(self, volttron_home=None):
#         os.chdir(rel_path) 
        self.tmpdir = tempfile.mkdtemp()
        self.wheelhouse = '/'.join((self.tmpdir, 'wheelhouse'))
        os.makedirs(self.wheelhouse)
        
        self.static_home = False
        if volttron_home is not None:
            mergetree(volttron_home, self.tmpdir)
            self.static_home = True
        self.env = os.environ.copy()
        self.env['VOLTTRON_HOME'] = self.tmpdir
         
        print (self.env['VOLTTRON_HOME'])
        
        if RESTRICTED_AVAILABLE:
            certsdir = os.path.join(os.path.expanduser(self.env['VOLTTRON_HOME']),
                                     'certificates')
            
            print ("certsdir", certsdir)
            self.certsobj = certs.Certs(certsdir)
        
        
    def startup_platform(self, platform_config=None, use_twistd = True, mode=UNRESTRICTED):
        
        try:
            if platform_config:
                config = json.loads(open(platform_config, 'r').read())
                config['tmpdir'] = self.tmpdir
            else:
                config = {}
        except Exception as e:
            sys.stderr.write (str(e))
        
#         self.tmpdir = tempfile.mkdtemp()
        pconfig = os.path.join(self.tmpdir, TMP_PLATFORM_CONFIG_FILENAME)
        
        self.mode = mode
        
        assert(self.mode in MODES, 'Invalid platform mode set: '+str(mode))
        
        opts = None
        
        if self.mode == UNRESTRICTED:
            if config:
                with closing(open(pconfig, 'w')) as cfg:
                    cfg.write(PLATFORM_CONFIG_UNRESTRICTED.format(**config))
            opts = type('Options', (), {'verify_agents': False,'volttron_home': self.tmpdir})()
        elif self.mode == RESTRICTED:
            if not RESTRICTED_AVAILABLE:
                raise ValueError("restricted is not available.")
            if config:
                with closing(open(pconfig, 'w')) as cfg:
                    cfg.write(PLATFORM_CONFIG_RESTRICTED.format(**config))
            opts = type('Options', (), {'verify_agents': True, 'volttron_home': self.tmpdir})()
            
#                 self.create_certs()
        else:
            
            self.fail("Platform mode not implemented: "+str(mode))
            
            
        self.test_aip = aip.AIPplatform(opts)
        self.test_aip.setup()
            

        tconfig = os.path.join(self.tmpdir, TMP_SMAP_CONFIG_FILENAME)

        lfile = os.path.join(self.tmpdir, "volttron.log")       
        
        pparams = [VSTART, "-c", pconfig, "-vv", "-l", lfile]
        print pparams
        print os.getcwd()
        self.p_process = subprocess.Popen(pparams, env=self.env)

        
        #Setup connector
        path = '{}/run/control'.format(self.env['VOLTTRON_HOME'])
        
        time.sleep(5)
        tries = 0
        max_tries = 5
        while(not os.path.exists(path) and tries < max_tries):
            time.sleep(5)
            tries += 1
             
        self.conn= server.ControlConnector(path)
 
 
#         if self.mode == RESTRICTED:
#             self.conn.call.create_cgroups()
        
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

#     def build_agentpackage(self, distdir):
#         pwd = os.getcwd()
#         try:
#             basepackage = os.path.join(self.tmpdir,distdir)
#             shutil.copytree(os.path.abspath(distdir), basepackage)
#             orignal_dir = os.getcwd()
#             os.chdir(basepackage)
#             sys.argv = ['', 'bdist_wheel']
#             exec(compile(open('setup.py').read(), 'setup.py', 'exec'))
#      
#             wheel_name = os.listdir('./dist')[0]
#      
#             wheel_file_and_path = os.path.join(os.path.abspath('./dist'), wheel_name)
#         finally:
#             os.chdir(orignal_dir)
#             
#         return wheel_file_and_path
    
    def direct_sign_agentpackage_creator(self, package):
        assert (RESTRICTED), "Auth not available"
        print ("wrapper.certsobj", self.certsobj.cert_dir)
        assert(auth.sign_as_creator(package, 'creator', certsobj=self.certsobj)), "Signing as {} failed.".format('creator')
            

    def direct_sign_agentpackage_admin(self, package):
        assert (RESTRICTED), "Auth not available"
        assert(auth.sign_as_admin(package, 'admin', certsobj=self.certsobj)), "Signing as {} failed.".format('admin')
            

    def direct_sign_agentpackage_initiator(self, package, config_file, contract):
        assert (RESTRICTED), "Auth not available"
        files = {"config_file":config_file,"contract":contract}
        assert(auth.sign_as_initiator(package, 'initiator', files=files, 
                                      certsobj=self.certsobj)), "Signing as {} failed.".format('initiator')
            

    
    def direct_build_agentpackage(self, agent_dir):
        wheel_path = packaging.create_package(os.path.join(rel_path, agent_dir), self.wheelhouse)
            
        return wheel_path
    
    def direct_send_agent(self, package, target):
        pparams = [VCTRL, SEND_AGENT, target, package]
        print (pparams, "CWD", os.getcwd())
        send_process = subprocess.call(pparams, env=self.env)
        print ("Done sending to", target)

    def direct_configure_agentpackage(self, agent_wheel, config_file):
        packaging.add_files_to_package(agent_wheel, {'config_file':os.path.join(rel_path, config_file)})
            


    def direct_buid_install_agent(self, agent_dir, config_file):
        agent_wheel = self.direct_build_agentpackage(agent_dir)
        self.direct_configure_agentpackage(agent_wheel, config_file)
        assert(agent_wheel is not None,"Agent wheel was not built")
        
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
    
    def direct_build_send_agent(self, agent_dir, config_file, target):
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
        assert status_uuid == agent_uuid
        
        assert len(status[0][2]) == 2, 'Unexpected agent status message'
        status_agent_status = status[0][2][1]
        assert not isinstance(status_agent_status, int)
#         self.assertIn("running",status_agent_status, "Agent status shows error")
        print status
        
    def confirm_agent_running(self, agent_name, max_retries=5, timeout_seconds=2):
        
#         self.test_aip.status_agents()
        
#         status = self.conn.call.status_agents()
#         self.assertEquals(len(status[0]), 4, 'Unexpected status message')
        running = False
        retries = 0
        while (not running and retries < max_retries):
            status = self.conn.call.status_agents()
            print ("Status", status)
            if len(status) > 0:
                status_name = status[0][1]
                assert status_name == agent_name
                
                assert len(status[0][2]) == 2, 'Unexpected agent status message'
                status_agent_status = status[0][2][1]
                running = not isinstance(status_agent_status, int)
            retries += 1
            time.sleep(timeout_seconds)
        return running

        
    def direct_stop_agent(self, agent_uuid):
        result = self.conn.call.stop_agent(agent_uuid)
        print result

            
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
#         if self.tmpdir != None:
#             shutil.rmtree(self.tmpdir, True)
    
    def cleanup(self):
        try:
            self.shutdown_platform()
        except Exception as e:
            sys.stderr.write( str(e))
        finally:
            pass
            
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

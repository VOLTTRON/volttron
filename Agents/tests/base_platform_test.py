import os
import shutil
import subprocess
import sys
import time
import tempfile

import unittest


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
# CONFIG_FILE = "test-config.ini"

class BasePlatformTest(unittest.TestCase):
    
    @classmethod
    def writePConfig(cls):
    
    @classmethod
    def setUpClass(cls):
        '''Setup platform here (only called on time per class)'''
        os.chdir('../../')
        
        cls.tempdir = tempfile.mkdtemp()
        
        
        
        cls.p_process = subprocess.Popen([VSTART])
#                                           "-c", CONFIG_FILE, "-v", "-l", "volttron.log"])
        cls.t_process = subprocess.Popen(["twistd", "-n", "smap", "test-smap.ini"])
        time.sleep(3)
    
    @classmethod
    def tearDownClass(cls):
        '''Stop platform here'''
        if cls.p_process != None:
            cls.p_process.kill()
        else: 
            print "NULL"
        
        if cls.t_process != None:
            cls.t_process.kill()
        else: 
            print "NULL"
            
        shutil.rmtree(cls.tempdir, True)
    
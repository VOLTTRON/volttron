
import os
import shutil
import subprocess
import sys
import time
import tempfile
import unittest

from contextlib import closing


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
SMAP_KEY_FILE = 'test-smap-key.ini'

PLATFORM_CONFIG = """
"""

TWISTED_CONFIG = """
"""

try:
    SMAP_KEY = open(SMAP_KEY_FILE, 'r').read()
except:
    sys.stderr.write("SMAP key file was not read\n")
    sys.stderr.write("It should be located at:\n\t{}".format(
                     os.path.abspath('../../../{}\n'.format(SMAP_KEY_FILE)))
                     )

class BasePlatformTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        '''Setup platform here (only called on time per class)'''
        os.chdir('../../')

        cls.tempdir = tempfile.mkdtemp()

        pconfig = os.path.join(cls.tmpdir, CONFIG_FILE)
        with closing(open(pconfig, 'w')) as cfg:
            cfg.write(PLATFORM_CONFIG)

        tconfig = os.path.join(cls.tmpdir, SMAP_FILE)
        with closing(open(tconfig, 'w')) as cfg:
            cfg.write(TWISTED_CONFIG.format(SMAP_KEY))

        lfile = os.path.join(cls.tmpdir, "volttron.log")

        cls.p_process = subprocess.Popen([VSTART, "-c", pconfig, "-v", "-l", lfile])
        cls.t_process = subprocess.Popen(["twistd", "-n", "smap", tconfig])
        #cls.t_process = subprocess.Popen(["twistd", "-n", "smap", "test-smap.ini"])
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

import subprocess
from subprocess import Popen
import os
import shutil
import sys

if not os.path.exists("volttron/platform"):
    print('please execute from root volttron directory.')
    sys.exit(0)

if not os.path.exists("env/bin/volttron"):
    print('please bootstrap and create environment for volttron')
    sys.exit(0)

vhomes = ["/tmp/v{}".format(i) for i in range(4)]

vc_address = "http://127.0.0.1:8080"+26
for i in range(len(vhomes)):
    home = vhomes[i]
    if os.path.exists(home):
        shutil.rmtree(home, True)

    os.makedirs(home)
    cmd = ["volttron", "-vv", "-l{}/{}".format(home, "volttron.log")]
    if i not in (0,):
        cmd.append("--volttron-central-address={}".format(vc_address))
    if i in (0,4):
        cmd.extend(["--bind-web-address=http://127.0.0.{}:8080".format(i)])

    cmd.append('--instance-name="volttron-platform-{}'.format(i))

    env = os.environ.copy()
    env['VOLTTRON_HOME'] = home

    process = Popen(cmd, env=env)
    print(process.pid)

    # A None value means that the process is still running.
    # A negative means that the process exited with an error.
    assert process.poll() is None
print(vhomes)
import os
import psutil
import subprocess

vhomes = ["/tmp/v{}".format(i) for i in range(1, 5)]

for h in vhomes:
    cmd = ['volttron-ctl', 'shutdown', '--platform']
    env = os.environ.copy()
    env['VOLTTRON_HOME'] = h
    resp = subprocess.check_call(cmd, env=env)

pidfile = os.path.join(os.path.dirname(__file__), "pids")
if os.path.exists(pidfile):
    with open(pidfile) as fin:
        for pid in fin:
            pid = int(pid)
            if psutil.pid_exists(pid):
                print('Killing VOLTTRON process {}'.format(
                    pid))
                p = psutil.Process(pid)
                p.terminate()  # or p.kill()

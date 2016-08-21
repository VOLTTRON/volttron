import json
import subprocess
from subprocess import Popen
import os
import psutil
import shutil
import sys
import tempfile


def setup_platform_1(env, home):
    """ Setup the first platform (volttron central).

    This platform will hold the following agents with identities in ()

    - VOLTTRON Central (volttron.central)
    - SQLHistorian - an sqlite historian (platform.historian)
    - VOLTTRON Central Platform (platform.agent)
    """

    agents = ["services/core/{}".format(p) for p in ("VolttronCentral",
                                                     "SQLHistorian",
                                                     "VolttronCentralPlatform")]
    tags = ['vc', 'ph', 'vcp']
    vip = ['volttron.central', 'platform.historian', 'platform.agent']

    configs = [
        {
            "users": {
                "admin": {
                    "password": "c7ad44cbad762a5da0a452f9e854fdc1e0e7a52a38015f23f3eab1d80b931dd472634dfac71cd34ebc35d16ab7fb8a90c81f975113d6c7538dc69dd8de9077ec",
                    "groups": [
                        "admin"
                    ]
                }
            }
        },
        {
            "agentid": "sqlhistorian",
            "connection": {
                "type": "sqlite",
                "params": {
                    "database": "{}/data/platform.historian.sqlite".format(home)
                }
            }
        },
        {}
    ]

    for i in range(len(agents)):
        cfgfile = "/tmp/config"

        with open(cfgfile, 'w') as cfgout:
            json.dump(configs[i], cfgout)

        cmd = ["volttron-pkg", "package", agents[i]]

        output = subprocess.check_output(cmd)
        filename = output.split(":")[1].strip()

        cmd = ["volttron-pkg", "configure", filename, cfgfile]
        output = subprocess.check_output(cmd)

        cmd = ["volttron-ctl", "install", filename, "--tag", tags[i],
               "--vip-identity", vip[i]]
        output = subprocess.check_output(cmd, env=env)

        cmd = ["volttron-ctl", "start", "--tag", tags[i]]
        output = subprocess.check_output(cmd, env=env)


def setup_platform_2(env, home):
    """ Setup the second platform.

    This platform will hold the following agents with identities in ()

    - VOLTTRON Central Platform (platform.agent)

    This platform should be automatically registered with volttron-central on
    the startup of the volttron central platform agent.
    """

    agents = ["services/core/{}".format(p) for p in ["VolttronCentralPlatform"]]
    tags = ['vcp']
    vip = ['platform.agent']

    configs = [
        {}
    ]

    for i in range(len(agents)):
        cfgfile = "/tmp/config"

        with open(cfgfile, 'w') as cfgout:
            json.dump(configs[i], cfgout)

        cmd = ["volttron-pkg", "package", agents[i]]

        output = subprocess.check_output(cmd)
        filename = output.split(":")[1].strip()

        cmd = ["volttron-pkg", "configure", filename, cfgfile]
        output = subprocess.check_output(cmd)

        cmd = ["volttron-ctl", "install", filename, "--tag", tags[i],
               "--vip-identity", vip[i]]
        output = subprocess.check_output(cmd, env=env)

        cmd = ["volttron-ctl", "start", "--tag", tags[i]]
        output = subprocess.check_output(cmd, env=env)


def main():
    vhomes = ["/tmp/v{}".format(i+1) for i in range(4)]
    envs = []
    pidfile = os.path.join(os.path.dirname(__file__), "pids")
    with open(pidfile, 'w') as pidout:
        vc_address = "http://127.0.0.1:8080"
        for x in range(len(vhomes)):
            i = x+1
            home = vhomes[x]
            if os.path.exists(home):
                shutil.rmtree(home, True)

            os.makedirs(home)
            cmd = ["volttron", "-vv", "-l{}/{}".format(home, "volttron.log"),
                   "--vip-address=tcp://127.0.0.{}:22916".format(i)]
            if i not in (1,4):
                cmd.append("--volttron-central-address={}".format(vc_address))
            if i in (1, 4):
                cmd.append(
                    "--bind-web-address=http://127.0.0.{}:8080".format(i))

            cmd.append('--instance-name="volttron-platform-{}"'.format(i))

            env = os.environ.copy()
            envs.append(env)
            env['VOLTTRON_HOME'] = home
            process = Popen(cmd, env=env)

            # A None value means that the process is still running.
            # A negative means that the process exited with an error.
            assert process.poll() is None

            pidout.write("{}\n".format(process.pid))

    setup_functions = [setup_platform_1, setup_platform_2]

    for i in range(len(setup_functions)):
        setup_functions[i](envs[i], vhomes[i])


if __name__=='__main__':

    if not os.path.exists("volttron/platform"):
        print('please execute from root volttron directory.')
        sys.exit(0)

    if not os.path.exists("env/bin/volttron"):
        print('please bootstrap and create environment for volttron')
        sys.exit(0)

    pidfile = os.path.join(os.path.dirname(__file__), "pids")
    if os.path.exists(pidfile):
        with open(pidfile) as fin:
            for pid in fin:
                pid = int(pid)
                if psutil.pid_exists(pid):
                    print('Removing previously run VOLTTRON process {}'.format(
                        pid))
                    p = psutil.Process(pid)
                    p.terminate()  # or p.kill()

    # Start the main platform
    main()

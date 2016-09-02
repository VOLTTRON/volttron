import json
import requests
import subprocess
from subprocess import Popen
import os
import psutil
import shutil
import sys
from time import sleep


vc_address = None


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
        install_agent(env, agents[i], configs[i], tags[i], vip[i])


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
        install_agent(env, agents[i], configs[i], tags[i], vip[i])


def setup_platform_3(env, home):
    """ Setup the third platform.

    This platform will hold the following agents with identities in ()

    - VOLTTRON Central Platform (platform.agent)
    - A forwarding agent that should forward to the volttron central instance.

    This platform should be automatically registered with volttron-central on
    the startup of the volttron central platform agent.
    """

    agents = ["services/core/{}".format(p) for p in ["VolttronCentralPlatform",
                                                     "ForwardHistorian"]]
    tags = ['vcp', 'forwarder']
    vip = ['platform.agent', 'forward.historian']

    configs = [
        {},
        {'destination-vip': get_destination_address(vc_address)}
    ]

    for i in range(len(agents)):
        install_agent(env, agents[i], configs[i], tags[i], vip[i])

#    install_fake_masterdriver(env, home)


def setup_platform_4(env, home):
    """ Setup the fourth platform.

    This platform will hold the following agents with identities in ()

    - VOLTTRON Central Platform (platform.agent)

    This platform won't be automatically registered with the volttron-central
    instances.
    """

    agents = ["services/core/{}".format(p) for p in ["VolttronCentralPlatform"]]
    tags = ['vcp']
    vip = ['platform.agent']

    configs = [
        {}
    ]

    for i in range(len(agents)):
        install_agent(env, agents[i], configs[i], tags[i], vip[i])


def install_fake_masterdriver(env, home):
    lines = [
        "Point Name, Volttron Point Name, Units, Units Details, Writable, Starting Value, Type, Notes",
        "Heartbeat, Heartbeat, On / Off, On / Off, TRUE, 0, boolean, Point for heartbeat toggle",
        "EKG, EKG, waveform, waveform, TRUE, 1, float, Sine wave for baseline output"]

    registrycfg = os.path.join(os.path.dirname(__file__), "registry.csv")
    registrycfg = os.path.abspath(registrycfg)
    with open(registrycfg, 'w') as fout:
        for line in lines:
            fout.write("{}\n".format(line))

    drivercfg = {
        "driver_config": {},
        "campus": "MyFakeCampus",
        "building": "SomeBuilding",
        "unit": "MyFakeDevice",
        "driver_type": "fakedriver",
        "registry_config": registrycfg,
        "interval": 5,
        "timezone": "US/Pacific",
        "heart_beat_point": "Heartbeat"
    }
    driverfile = os.path.join(os.path.dirname(__file__), "driver.cfg")
    driverfile = os.path.abspath(driverfile)
    with open(driverfile, 'w') as fout:
        json.dump(drivercfg, fout, indent=4)

    masterdrivercfg = {
        "agentid": "master_driver",
        "driver_config_list": [driverfile]
    }

    masterdriver = os.path.join(os.path.dirname(__file__), "masterdriver.cfg")
    masterdriver = os.path.abspath(masterdriver)
    with open(masterdriver, 'w') as fout:
        json.dump(masterdrivercfg, fout, indent=4)

    install_agent(env, "services/core/MasterDriverAgent", masterdriver,
                  "driver")


def install_agent(env, agent_dir, cfgdict, tag, identity=None):
    cfgfile = "/tmp/config"

    with open(cfgfile, 'w') as cfgout:
        json.dump(cfgdict, cfgout)

    cmd = ["volttron-pkg", "package", agent_dir]

    output = subprocess.check_output(cmd)
    print(output)
    filename = output.split(":")[1].strip()

    cmd = ["volttron-pkg", "configure", filename, cfgfile]
    output = subprocess.check_output(cmd)

    cmd = ["volttron-ctl", "install", filename, "--tag", tag]
    if identity:
        cmd.extend(["--vip-identity", identity])
    output = subprocess.check_output(cmd, env=env)

    cmd = ["volttron-ctl", "start", "--tag", tag]
    output = subprocess.check_output(cmd, env=env)


def main():
    global vc_address
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

            # for instance 1 and 4 we have web support.  instance 1 is where
            # vc lives as well as the vcp.  instance 4 is available to use
            # the discovery button through the volttron central interface.
            if i in (1, 4):
                cmd.append(
                    "--bind-web-address=http://127.0.0.{}:8080".format(i))

            # for instance 2 we use volttron-central-address to auto register
            # with volttron central.
            if i == 2:
                cmd.append("--volttron-central-address={}".format(
                    vc_address))

            # instance 3 uses the volttron central tcp address and serverkey
            # to auto register it.
            if i == 3:
                cmd.append("--volttron-central-address={}".format(
                    get_vc_vipaddress(vc_address)))
                cmd.append("--volttron-central-serverkey={}".format(
                    get_vc_serverkey(vc_address)
                ))

            cmd.append('--instance-name=volttron-platform-{}'.format(i))

            env = os.environ.copy()
            envs.append(env)
            env['VOLTTRON_HOME'] = home
            process = Popen(cmd, env=env)

            # A None value means that the process is still running.
            # A negative means that the process exited with an error.
            assert process.poll() is None

            pidout.write("{}\n".format(process.pid))
            sleep(0.4)

    setup_functions = [setup_platform_1, setup_platform_2, setup_platform_3,
                       setup_platform_4]

    for i in range(len(setup_functions)):
        setup_functions[i](envs[i], vhomes[i])


def get_vc_serverkey(vc_address):
    resp = requests.get("{}/discovery/".format(vc_address))
    d = resp.json()
    return d['serverkey']


def get_vc_vipaddress(vc_address):
    resp = requests.get("{}/discovery/".format(vc_address))
    d = resp.json()
    return d['vip-address']


def get_destination_address(vc_address):
    resp = requests.get("{}/discovery/".format(vc_address))
    d = resp.json()
    return "{vip-address}?serverkey={serverkey}".format(**d)

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

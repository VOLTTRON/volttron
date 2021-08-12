from collections import namedtuple
from multiprocessing import Process
import select
import shutil
import subprocess
from subprocess import PIPE, STDOUT
import sys
import tempfile
from typing import NamedTuple
import os

import gevent


class VolttronRuntimeOptions(NamedTuple):
    message_bus: str = 'ZMQ'
    web_enabled: bool = False
    https_enabled: bool = False


class VolttronProcess(Process):

    def __init__(self, print_output=True,
                 exclude_timestamp=True,
                 runtime_options: VolttronRuntimeOptions = None):
        super(VolttronProcess, self).__init__(target=self.__target)
        self.daemon = True
        # Create a home directory for VOLTTRON_HOME
        self.volttron_home = tempfile.mkdtemp()

        # Create a copy of the current environment and use the passed environment
        # throughout the process creation
        self._my_env = os.environ.copy()
        self._my_env['VOLTTRON_HOME'] = self.volttron_home
        self._print_output = print_output
        self._exlude_timestamp = exclude_timestamp
        self._keep_volttron_home = False
        self._runtime_options = runtime_options
        self._volttron_subprocess = None

    @property
    def environment(self):
        return self._my_env.copy()

    def update_environment(self, key, value):
        self._my_env[key] = value

    @property
    def keep_volttron_home(self):
        return self._keep_volttron_home

    @keep_volttron_home.setter
    def keep_volttron_home(self, value):
        self._keep_volttron_home = value

    def __target(self):
        invalid_runtime = self.validate_runtime(self._runtime_options)
        if invalid_runtime:
            sys.stderr.write('Invalid runtime options specified\n')
            for v in invalid_runtime:
                sys.stderr.write(v + '\n')
            sys.exit(1)

        with open(os.path.join(self.volttron_home, "volttron.log"), "w", encoding='utf-8') as fw:
            process = subprocess.Popen(["volttron", "-vv"],
                                       env=self._my_env, stderr=STDOUT, stdout=PIPE)
            self._volttron_subprocess = process
            skip = len('2019-07-12 18:51:02,702 ()')
            folder = self.volttron_home[5:]
            while process.poll() is None:
                results = select.select([process.stdout], [], [], 0)
                if results[0]:
                    line = results[0][0].readline()
                    while line:
                        line = line.decode('utf-8')
                        if self._print_output:
                            sys.stdout.write(folder + line[skip:])

                        fw.write(line)
                        line = results[0][0].readline()

            results = select.select([process.stdout], [], [], 0)
            if results[0]:
                line = results[0][0].readline()
                while line:
                    line = line.decode('utf-8')
                    if self._print_output:
                        sys.stdout.write(line)

                    fw.write(line)
                    line = results[0][0].readline()

    def shutdown(self):
        #if self._volttron_subprocess.poll() is None:
        # proc = subprocess.Popen(['vctl', 'shutdown', '--platform'],
        #                env=self._my_env, stdout=PIPE, stderr=STDOUT)
        #
        # while proc.poll() is None:
        #     gevent.sleep(0)
        print("Done with proc")
        #
        subprocess.run(['vctl', 'shutdown', '--platform'],
                       env=self._my_env, stdout=PIPE, stderr=STDOUT)
        if not self.keep_volttron_home:
            shutil.rmtree(self.volttron_home, ignore_errors=True)

    @staticmethod
    def validate_runtime(runtime: VolttronRuntimeOptions):
        validation_errors = []

        if runtime.message_bus not in ('ZMQ', 'RMQ'):
            validation_errors.append(f'Invalid message bus type: {runtime.message_bus} should be either RMQ or ZMQ')

        return validation_errors


class AgentProcess(Process):

    def __init__(self, agent_source, volttron_home, config):
        super(AgentProcess, self).__init__(target=self.__target)
        self.daemon = True
        self._agent_source = agent_source
        self._volttron_home = volttron_home
        self._config = config
        self._my_env = os.environ.copy()
        self._my_env['AGENT_CONFIG'] = config
        self._my_env['VOLTTRON_HOME'] = volttron_home

    def __target(self):
        process = subprocess.run(["python", self._agent_source],
                                 cwd="/home/osboxes/repos/volttron-develop/examples/ListenerAgent",
                                 env=self._my_env, stderr=PIPE, stdout=PIPE)
        print(self.__class__.__name__)
        print(process.stdout)
        print(process.stderr)
        print(process.returncode)

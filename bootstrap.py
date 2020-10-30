# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

"""bootstrap - Prepare a VOLTTRON virtual environment.

Bootstrapping is broken into two stages. The first stage should only be
invoked once per virtual environment. It downloads virtualenv and
creates a virtual Python environment in the virtual environment
directory (defaults to a subdirectory named env in the same directory as
this script). It then executes stage two using the newly installed
virtual environment. Stage two uses the new virtual Python environment
to install VOLTTRON and its dependencies.

If a new dependency is added, this script may be run again using the
Python executable in the virtual environment to re-run stage two:

  env/bin/python bootstrap.py

To speed up bootstrapping in a test environment, use the --wheel
feature, which might look something like this:

  $ export PIP_WHEEL_DIR=/path/to/cache/wheelhouse
  $ export PIP_FIND_LINKS=file://$PIP_WHEEL_DIR
  $ mkdir -p $PIP_WHEEL_DIR
  $ python2.7 bootstrap.py -o
  $ env/bin/python bootstrap.py --wheel
  $ env/bin/python bootstrap.py

Instead of setting the environment variables, a pip configuration file
may be used. Look here for more information on configuring pip:

  https://pip.pypa.io/en/latest/user_guide.html#configuration

"""


import argparse
import errno
import logging
import subprocess
import sys
from urllib.request import urlopen

import os
import traceback

from requirements import extras_require, option_requirements

_log = logging.getLogger(__name__)

_WINDOWS = sys.platform.startswith('win')
default_rmq_dir = os.path.join(os.path.expanduser("~"), "rabbitmq_server")
rabbitmq_server = 'rabbitmq_server-3.7.7'


def shescape(args):
    '''Return a sh shell escaped string composed of args.'''
    return ' '.join('{1}{0}{1}'.format(arg.replace('"', '\\"'),
                    '"' if ' ' in arg else '') for arg in args)


def bootstrap(dest, prompt='(volttron)', version=None, verbose=None):
    import shutil
    args = [sys.executable, "-m", "venv", dest, "--prompt", prompt]

    complete = subprocess.run(args, stdout=subprocess.PIPE)
    if complete.returncode != 0:
        sys.stdout.write(complete.stdout.decode('utf-8'))
        shutil.rmtree(dest, ignore_errors=True)
        sys.exit(1)

    return os.path.join(dest, "bin/python")


def pip(operation, args, verbose=None, upgrade=False, offline=False):
    """Call pip in the virtual environment to perform operation."""
    cmd = ['pip', operation]
    if verbose is not None:
        cmd.append('--verbose' if verbose else '--quiet')
    if upgrade and operation == 'install':
        cmd.append('--upgrade')
    if offline:
        cmd.extend(['--retries', '0', '--timeout', '1'])
    cmd.extend(args)
    _log.info('+ %s', shescape(cmd))
    cmd[:0] = [sys.executable, '-m']
    subprocess.check_call(cmd)


def update(operation, verbose=None, upgrade=False, offline=False, optional_requirements=[], rabbitmq_path=None):
    """Install dependencies in setup.py and requirements.txt."""
    print("UPDATE: {}".format(optional_requirements))
    assert operation in ['install', 'wheel']
    wheeling = operation == 'wheel'
    path = os.path.dirname(__file__) or '.'
    _log.info('%sing required packages', 'Build' if wheeling else 'Install')

    # We must install wheel first to eliminate a bunch of scary looking
    # errors at first install.
    # TODO Look towards fixing the packaging so that it works with 0.31
    pip('install', ['wheel==0.30'], verbose, True, offline=offline)

    # Build option_requirements separately to pass install options
    build_option = '--build-option' if wheeling else '--install-option'
    for requirement, options in option_requirements:
        args = []
        for opt in options:
            args.extend([build_option, opt])
        args.extend(['--no-deps', requirement])
        pip(operation, args, verbose, upgrade, offline)

    # Install local packages and remaining dependencies
    args = []
    target = path
    if optional_requirements:
        target += '[' + ','.join(optional_requirements) + ']'
    args.extend(['--editable', target])
    pip(operation, args, verbose, upgrade, offline)

    try:
        # Install rmq server if needed
        if rabbitmq_path:
            install_rabbit(rabbitmq_path)
    except Exception as exc:
        _log.error("Error installing RabbitMQ package {}".format(traceback.format_exc()))


def install_rabbit(rmq_install_dir):
    # Install gevent friendly pika
    pip('install', ['gevent-pika==0.3'], False, True, offline=False)
    # try:
    process = subprocess.Popen(["which", "erl"], stderr=subprocess.PIPE,  stdout=subprocess.PIPE)
    (output, error) = process.communicate()
    if process.returncode != 0:
        sys.stderr.write("ERROR:\n Unable to find erlang in path. Please install necessary pre-requisites. "
                "Reference: https://volttron.readthedocs.io/en/latest/setup/index.html#steps-for-rabbitmq")

        sys.exit(60)

    if rmq_install_dir == default_rmq_dir and not os.path.exists(
            default_rmq_dir):
        os.makedirs(default_rmq_dir)
        _log.info("\n\nInstalling Rabbitmq Server in default directory: " +
                  default_rmq_dir)
    else:
        _log.info(
            "\n\nInstalling Rabbitmq Server at {}".format(rmq_install_dir))

    valid_dir = os.access(rmq_install_dir, os.W_OK)
    if not valid_dir:
        raise ValueError("Invalid install directory. Directory should "
                         "exist and should have write access to user")

    rmq_home = os.path.join(rmq_install_dir, rabbitmq_server)
    if os.path.exists(rmq_home) and \
            os.path.exists(os.path.join(rmq_home, 'sbin/rabbitmq-server')):
        _log.info("{} already contains {}. "
              "Skipping rabbitmq server install".format(
            rmq_install_dir, rabbitmq_server))
    else:
        url = "https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.7.7/rabbitmq-server-generic-unix-3.7.7.tar.xz"
        f = urlopen(url)
        data = f.read()
        filename = "rabbitmq-server.download.tar.xz"
        with open(filename, "wb") as imgfile:
            imgfile.write(data)
        _log.info("\nDownloaded rabbitmq server")
        cmd = ["tar",
               "-xf",
               filename,
               "--directory=" + rmq_install_dir]
        subprocess.check_call(cmd)
        _log.info("Installed Rabbitmq server at " + rmq_home)
    # enable plugins
    cmd = [os.path.join(rmq_home, "sbin/rabbitmq-plugins"),
           "enable", "rabbitmq_management",
           "rabbitmq_federation",
           "rabbitmq_federation_management",
           "rabbitmq_shovel",
           "rabbitmq_shovel_management",
           "rabbitmq_auth_mechanism_ssl",
           "rabbitmq_trust_store"]
    subprocess.check_call(cmd)

    with open(os.path.expanduser("~/.volttron_rmq_home"), 'w+') as f:
        f.write(rmq_home)


def main(argv=sys.argv):
    """Script entry point."""

    # Refuse to run as root
    if not getattr(os, 'getuid', lambda: -1)():
        sys.stderr.write('%s: error: refusing to run as root to prevent '
                         'potential damage.\n' % os.path.basename(argv[0]))
        sys.exit(77)

    # Python3 for life!
    if sys.version_info.major < 3 or sys.version_info.minor < 6:
        sys.stderr.write('error: Python >= 3.6 is required\n')
        sys.exit(1)

    # Build the parser
    python = os.path.join('$VIRTUAL_ENV',
                          'Scripts' if _WINDOWS else 'bin', 'python')
    if _WINDOWS:
        python += '.exe'
    parser = argparse.ArgumentParser(
        description='Bootstrap and update a virtual Python environment '
                    'for VOLTTRON development.',
        usage='\n  bootstrap: python3.6 %(prog)s [options]'
              '\n  update:    {} %(prog)s [options]'.format(python),
        prog=os.path.basename(argv[0]),
        epilog="""
            The first invocation of this script, which should be made
            using the system Python, will create a virtual Python
            environment in the 'env' subdirectory in the same directory as
            this script or in the directory given by the --envdir option.
            Subsequent invocations of this script should use the Python
            executable installed in the virtual environment."""
    )
    verbose = parser.add_mutually_exclusive_group()
    verbose.add_argument(
        '-q', '--quiet', dest='verbose', action='store_const', const=False,
        help='produce less output')
    verbose.add_argument(
        '-v', '--verbose', action='store_const', const=True,
        help='produce extra output')
    bs = parser.add_argument_group('bootstrap options')
    bs.add_argument(
        '--envdir', default=None, metavar='VIRTUAL_ENV',
        help='alternate location for virtual environment')
    bs.add_argument(
        '--force', action='store_true', default=False,
        help='force installing in non-empty directory')
    bs.add_argument(
        '-o', '--only-virtenv', action='store_true', default=False,
        help='create virtual environment and exit (skip install)')
    bs.add_argument(
        '--prompt', default='volttron', help='provide alternate prompt '
        'in activated environment (default: %(default)s)')
    bs.add_argument('--force-version', help=argparse.SUPPRESS)

    # allows us to look and see if any of the dynamic optional arguments
    # are on the command line.  We check this during the processing of the args
    # variable at the end of the block.  If the option is set then it needs
    # to be passed on.
    po = parser.add_argument_group('Extra packaging options')
    for arg in extras_require:
        po.add_argument('--'+arg, action='append_const', const=arg, dest="optional_args")

    # Add rmq download actions.
    rabbitmq = parser.add_argument_group('rabbitmq options')
    rabbitmq.add_argument(
        '--rabbitmq', action='store', const=default_rmq_dir,
        nargs='?',
        help='install rabbitmq server and its dependencies. '
             'optional argument: Install directory '
             'that exists and is writeable. RabbitMQ server '
             'will be installed in a subdirectory.'
             'Defaults to ' + default_rmq_dir)

    #optional_args = []
    # if os.path.exists('optional_requirements.json'):
    #     po = parser.add_argument_group('Extra packaging options')
    #     with open('optional_requirements.json', 'r') as optional_arguments:
    #         data = jsonapi.load(optional_arguments)
    #         for arg, vals in data.items():
    #             if arg == '--rabbitmq':
    #                 po.add_argument(
    #                     '--rabbitmq', action='store', const=default_rmq_dir,
    #                     nargs='?',
    #                     help='install rabbitmq server and its dependencies. '
    #                          'optional argument: Install directory '
    #                          'that exists and is writeable. RabbitMQ server '
    #                          'will be installed in a subdirectory.'
    #                          'Defaults to ' + default_rmq_dir)
    #             else:
    #                 optional_args.append(arg)
    #                 if 'help' in vals.keys():
    #                     po.add_argument(arg, action='store_true', default=False,
    #                                     help=vals['help'])
    #                 else:
    #                     po.add_argument(arg, action='store_true', default=False)

    # Update options
    up = parser.add_argument_group('update options')
    up.add_argument(
        '--offline', action='store_true', default=False,
        help='install from cache without downloading')
    ex = up.add_mutually_exclusive_group()
    ex.add_argument(
        '-u', '--upgrade', action='store_true', default=False,
        help='upgrade installed packages')
    ex.add_argument(
        '-w', '--wheel', action='store_const', const='wheel', dest='operation',
        help='build wheels in the pip wheelhouse')
    path = os.path.dirname(__file__) or os.getcwd()
    parser.set_defaults(envdir=os.path.join(path, 'env'), operation='install', optional_args=[])
    options = parser.parse_args(argv[1:])

    # Route errors to stderr, info and debug to stdout
    error_handler = logging.StreamHandler(sys.stderr)
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    info_handler = logging.StreamHandler(sys.stdout)
    info_handler.setLevel(logging.DEBUG)
    info_handler.setFormatter(logging.Formatter('%(message)s'))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if options.verbose else logging.INFO)
    root.addHandler(error_handler)
    root.addHandler(info_handler)

    # Main script logic to perform bootstrapping or updating
    if sys.base_prefix != sys.prefix:
        # The script was called from a virtual environment Python, so update
        update(options.operation, options.verbose,
               options.upgrade, options.offline, options.optional_args, options.rabbitmq)
    else:
        # The script was called from the system Python, so bootstrap
        try:
            # Refuse to create environment in existing, non-empty
            # directory without the --force flag.
            if os.path.exists(options.envdir):
                if not options.force:
                    parser.print_usage(sys.stderr)
                    print('{}: error: directory exists and is not empty: {}'
                          .format(parser.prog, options.envdir), file=sys.stderr)
                    print('Use the virtual Python to update or use '
                          'the --force option to overwrite.', file=sys.stderr)
                    parser.exit(1)
                _log.warning('using non-empty environment directory: %s',
                             options.envdir)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise
        env_exe = bootstrap(options.envdir, options.prompt)
        if options.only_virtenv:
            return
        # Run this script within the virtual environment for stage2
        args = [env_exe, __file__]
        if options.verbose is not None:
            args.append('--verbose' if options.verbose else '--quiet')

        if options.rabbitmq is not None:
            args.append('--rabbitmq={}'.format(options.rabbitmq))

        # Transfer dynamic properties to the subprocess call 'update'.
        # Clip off the first two characters expecting long parameter form.
        for arg in options.optional_args:
            args.append('--'+arg)
        subprocess.check_call(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

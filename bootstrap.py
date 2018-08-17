# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

'''bootstrap - Prepare a VOLTTRON virtual environment.

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

'''


from __future__ import print_function

import argparse
import errno
import json
import logging
import subprocess
import sys

import os
from distutils.version import LooseVersion

_log = logging.getLogger(__name__)

_WINDOWS = sys.platform.startswith('win')


def shescape(args):
    '''Return a sh shell escaped string composed of args.'''
    return ' '.join('{1}{0}{1}'.format(arg.replace('"', '\\"'),
                    '"' if ' ' in arg else '') for arg in args)


def bootstrap(dest, prompt='(volttron)', version=None, verbose=None):
    '''Download latest virtualenv and create a virtual environment.

    The virtual environment will be created in the given directory. The
    shell prompt in the virtual environment can be overridden by setting
    prompt and a specific version of virtualenv can be used by passing
    the version string into version.
    '''
    # Imports used only for bootstrapping the environment
    import contextlib
    import shutil
    import tarfile
    import tempfile
    import urllib2

    class EnvBuilder(object):
        '''Virtual environment builder.

        The resulting python executable will be set in the env_exe
        attribute.
        '''

        __slots__ = ['version', 'prompt', 'env_exe']

        def __init__(self, version=None, prompt=None):
            '''Allow overriding version and prompt.'''
            self.version = version
            self.prompt = prompt
            self.env_exe = None

        def _fetch(self, url):
            '''Open url and return the response object (or bail).'''
            _log.debug('Fetching %s', url)
            response = urllib2.urlopen(url)
            if response.getcode() != 200:
                _log.error('Server response is %s %s',
                           response.code, response.msg)
                _log.fatal('Download failed!')
                sys.exit(1)
            return response

        def _url_available(self, url):
            '''Open url and if response is 200 then return True else return False'''
            _log.debug('Checking url %s', url)
            try:
                response = urllib2.urlopen(url)
                if response.getcode() != 200:
                    return False
            except urllib2.HTTPError:
                return False
            return True

        def get_version(self):
            """Return the latest version from virtualenv DOAP record."""
            _log.info('Downloading virtualenv package information')
            default_version = "15.1.0"
            url = 'https://pypi.python.org/pypi/virtualenv/json'
            with contextlib.closing(self._fetch(url)) as response:
                result = json.load(response)
                releases_dict = result.get("releases", {})
                releases = sorted(
                    [LooseVersion(x) for x in releases_dict.keys()])
            if releases:
                _log.info('latest release of virtualenv={}'.format(releases[-1]))
                return str(releases[-1])
            else:
                _log.info("Returning default version of virtualenv "
                          "({})".format(default_version))
                return default_version

        def download(self, directory):
            '''Download the virtualenv tarball into directory.'''
            if self.version is None:
                self.version = self.get_version()
            url = ('https://pypi.python.org/packages/source/v/virtualenv/'
                   'virtualenv-{}.tar.gz'.format(self.version))
            _log.info('Downloading virtualenv %s', self.version)
            tarball = os.path.join(directory, 'virtualenv.tar.gz')
            with contextlib.closing(self._fetch(url)) as response:
                with open(tarball, 'wb') as file:
                    shutil.copyfileobj(response, file)
            with contextlib.closing(tarfile.open(tarball, 'r|gz')) as archive:
                archive.extractall(directory)

        def create(self, directory, verbose=None):
            '''Create a virtual environment in directory.'''
            tmpdir = tempfile.mkdtemp()
            try:
                self.download(tmpdir)
                args = [sys.executable]
                args.append(os.path.join(tmpdir, 'virtualenv-{}'.format(
                    self.version), 'virtualenv.py'))
                if verbose is not None:
                    args.append('--verbose' if verbose else '--quiet')
                if self.prompt:
                    args.extend(['--prompt', prompt])
                args.append(directory)
                _log.debug('+ %s', shescape(args))
                subprocess.check_call(args)
                if _WINDOWS:
                    self.env_exe = os.path.join(
                        directory, 'Scripts', 'python.exe')
                else:
                    self.env_exe = os.path.join(directory, 'bin', 'python')
                assert(os.path.exists(self.env_exe))
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

    _log.info('Creating virtual Python environment')
    builder = EnvBuilder(prompt=prompt, version=version)
    builder.create(dest, verbose)
    return builder.env_exe


def pip(operation, args, verbose=None, upgrade=False, offline=False):
    '''Call pip in the virtual environment to perform operation.'''
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


def update(operation, verbose=None, upgrade=False, offline=False):
    '''Install dependencies in setup.py and requirements.txt.'''
    from setup import (option_requirements, local_requirements,
                       optional_requirements)
    assert operation in ['install', 'wheel']
    wheeling = operation == 'wheel'
    path = os.path.dirname(__file__) or '.'
    _log.info('%sing required packages', 'Build' if wheeling else 'Install')
    if wheeling:
        try:
            import wheel
        except ImportError:
            # wheel version 0.31 breaks packaging.
            # TODO Look towards fixing the packaging so that it works with 0.31
            pip('install', ['wheel==0.30'], verbose, offline=offline)
    # Downgrade wheel if necessary so things don't break.
    # TODO Fix hard coded version in this spot...should be somewhere else.
    pip('install', ['wheel==0.30'], verbose, offline=offline)

    # Build option_requirements separately to pass install options
    build_option = '--build-option' if wheeling else '--install-option'
    for requirement, options in option_requirements:
        args = []
        for opt in options:
            args.extend([build_option, opt])
        args.extend(['--no-deps', requirement])
        pip(operation, args, verbose, upgrade, offline)
    # Build the optional requirements that the user specified via the command
    # line.
    for requirement in optional_requirements:
        pip('install', [requirement], verbose, upgrade, offline)
    # Install local packages and remaining dependencies
    args = []
    for _, location in local_requirements:
        args.extend(['--editable', os.path.join(path, location)])
    args.extend(['--editable', path])
    requirements_txt = os.path.join(path, 'requirements.txt')
    if os.path.exists(requirements_txt):
        args.extend(['--requirement', requirements_txt])
    pip(operation, args, verbose, upgrade, offline)


def main(argv=sys.argv):
    '''Script entry point.'''

    # Refuse to run as root
    if not getattr(os, 'getuid', lambda: -1)():
        sys.stderr.write('%s: error: refusing to run as root to prevent '
                         'potential damage.\n' % os.path.basename(argv[0]))
        sys.exit(77)

    # Unfortunately, many dependencies are not yet available in Python3.
    if sys.version_info[:2] != (2, 7):
        sys.stderr.write('error: Python 2.7 is required\n')
        sys.exit(1)

    # Build the parser
    python = os.path.join('$VIRTUAL_ENV',
                          'Scripts' if _WINDOWS  else 'bin', 'python')
    if _WINDOWS:
        python += '.exe'
    parser = argparse.ArgumentParser(
        description='Bootstrap and update a virtual Python environment '
                    'for VOLTTRON development.',
        usage='\n  bootstrap: python2.7 %(prog)s [options]'
              '\n  update:    {} %(prog)s [options]'.format(python),
        prog=os.path.basename(argv[0]),
        epilog='''
            The first invocation of this script, which should be made
            using the system Python, will create a virtual Python
            environment in the 'env' subdirectory in the same directory as
            this script or in the directory given by the --envdir option.
            Subsequent invocations of this script should use the Python
            executable installed in the virtual environment.'''
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
        '--prompt', default='(volttron)', help='provide alternate prompt '
        'in activated environment (default: %(default)s)')
    bs.add_argument('--force-version', help=argparse.SUPPRESS)

    # allows us to look and see if any of the dynamic optional arguments
    # are on the command line.  We check this during the processing of the args
    # variable at the end of the block.  If the option is set then it needs
    # to be passed on.
    optional_args = []
    if os.path.exists('optional_requirements.json'):
        po = parser.add_argument_group('Extra packaging options')
        with open('optional_requirements.json', 'r') as optional_arguments:
            data = json.load(optional_arguments)
            for arg, vals in data.items():
                optional_args.append(arg)
                if 'help' in vals.keys():
                    po.add_argument(arg, action='store_true', default=False,
                                    help=vals['help'])
                else:
                    po.add_argument(arg, action='store_true', default=False)

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
    parser.set_defaults(envdir=os.path.join(path, 'env'), operation='install')
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
    if hasattr(sys, 'real_prefix'):
        # The script was called from a virtual environment Python, so update
        update(options.operation, options.verbose,
               options.upgrade, options.offline)
    else:
        # The script was called from the system Python, so bootstrap
        try:
            # Refuse to create environment in existing, non-empty
            # directory without the --force flag.
            if os.listdir(options.envdir):
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
        env_exe = bootstrap(options.envdir, options.prompt,
                            options.force_version, options.verbose)
        if options.only_virtenv:
            return
        # Run this script within the virtual environment for stage2
        args = [env_exe, __file__]
        if options.verbose is not None:
            args.append('--verbose' if options.verbose else '--quiet')
        # Transfer dynamic properties to the subprocess call 'update'.
        # Clip off the first two characters expecting long parameter form.
        for arg in optional_args:
            if getattr(options, arg[2:]):
                args.append(arg)
        subprocess.check_call(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

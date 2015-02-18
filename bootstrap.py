# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

from __future__ import print_function

import argparse
import errno
import logging
import os
import subprocess
import sys


_log = logging.getLogger(__name__)

_WINDOWS = sys.platform.startswith('win')


def check_call(args):
    '''Run a subprocess exiting if an error occurs.'''
    result = subprocess.call(args)
    if result:
        sys.exit(result)


def shescape(args):
    '''Return a sh shell escaped string composed of args.'''
    return ' '.join('{1}{0}{1}'.format(arg.replace('"', '\\"'),
                    '"' if ' ' in arg else '') for arg in args)


def bootstrap_virtenv(dest, prompt='(volttron)',
                      version=None, verbose=None):
    '''Download latest virtualenv and create a virtual environment.

    The virtual environment will be created in the given directory. The
    shell prompt in the virtual environment can be overridden by setting
    prompt and a specific version of virtualenv can be used by passing
    the version string into version.
    '''
    # Imports used only for bootstrapping the environment
    import contextlib
    import re
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

        def get_version(self):
            '''Return the latest version from virtualenv DOAP record.'''
            _log.info('Downloading virtualenv DOAP record')
            doap_url = ('https://pypi.python.org/pypi'
                        '?:action=doap&name=virtualenv')
            with contextlib.closing(self._fetch(doap_url)) as response:
                doap_xml = response.read()
            self.version = re.search(
                r'<revision>([^<]*)</revision>', doap_xml).group(1)
            return self.version

        def download(self, directory):
            '''Download the virtualenv tarball into directory.'''
            if self.version is None:
                self.get_version()
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
                if verbose:
                    args.append('--verbose')
                elif verbose is not None:
                    args.append('--quiet')
                if self.prompt:
                    args.extend(['--prompt', prompt])
                args.append(directory)
                _log.debug('+ %s', shescape(args))
                check_call(args)
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


def split_requirement(req):
    '''Return package name (without version) and requirement tuple.'''
    for i, c in enumerate(req):
        if not c.isalnum() and c not in '.-_':
            return req[:i].lower(), req
    return req.lower(), req


def get_requirements(requirements_path=None):
    '''Get a list for requirements from setup.py.

    Optional requirements file may also be parsed.

    Returns a dictionary with package names as key.
    '''
    from setup import install_requires
    class ReqDict(dict):
        def __missing__(self, key):
            return self.get(key.lower(), key)
    results = ReqDict(split_requirement(req) for req in install_requires)
    if requirements_path and os.path.exists(requirements_path):
        with open(requirements_path) as file:
            results.update(dict(split_requirement(req) for req in
                                (line.strip() for line in file)
                                if req and not req.startswith('#')))
    return results


def call_module(args):
    '''Call a python module with the given args in a separate process.

    Exit if the return code is non-zero.
    '''
    _log.info('+ %s', shescape(args))
    check_call([sys.executable, '-m'] + args)


def pip_install(args, verbose=None, upgrade=False):
    '''Call virtual environment `pip install`.'''
    cmd = ['pip', 'install']
    if verbose:
        cmd.extend(['--verbose', '--global-option', '--verbose'])
    elif verbose is None:
        cmd.extend(['--global-option', '--quiet'])
    else:
        cmd.extend(['--quiet', '--global-option', '--quiet'])
    if upgrade:
        cmd.append('--upgrade')
    cmd.extend(args)
    call_module(cmd)


def easy_install(args, verbose=None, upgrade=False):
    '''Call virtual environment easy_install.'''
    cmd = ['easy_install']
    if verbose:
        cmd.append('--verbose')
    elif verbose is not None:
        cmd.append('--quiet')
    if upgrade:
        cmd.append('--upgrade')
    cmd.extend(args)
    call_module(cmd)


def install(verbose=False):
    '''Install dependencies in setup.py and requirements.txt.'''
    path = os.path.dirname(__file__) or '.'
    _log.info('Installing required packages')
    requirements_txt = os.path.join(path, 'requirements.txt')
    requirements = get_requirements(requirements_txt)
    # Upgrade pip to avoid warning upgrade messages
    pip_install(['pip'], verbose, True)
    # Get bacpypes with easy_install, because it is only provided as an egg
    easy_install([requirements['BACpypes']], verbose)
    # Build pyzmq separately to pass install options
    pip_install(
        ['--install-option', '--zmq=bundled', requirements['pyzmq']], verbose)
    # Install local packages and remaining dependencies
    args = ['--editable', os.path.join(path, 'lib', 'jsonrpc'),
            '--editable', os.path.join(path, 'lib', 'clock'),
            '--editable', path]
    if os.path.exists(requirements_txt):
        args.extend(['--requirement', requirements_txt])
    pip_install(args, verbose)


def upgrade(packages, verbose=False):
    '''Upgrade installed packages.

    packages should be a list of packages to be upgraded or evaluate to
    False to upgrade all packages. If the first element in packages is
    '!', all packages except those in packages[1:] will be upgraded.
    '''
    from pip.utils import get_installed_distributions
    path = os.path.dirname(__file__) or '.'
    requirements = get_requirements(os.path.join(path, 'requirements.txt'))
    if packages and packages[0] != '!':
        packages = {name.lower(): requirements[name] for name in packages}
    else:
        exclude = packages[1:] if packages else []
        exclude.extend(['volttron', 'flexible-jsonrpc', 'posix-clock'])
        packages = {dist.project_name.lower(): requirements[dist.project_name]
                    for dist in
                        get_installed_distributions(include_editables=False)}
        for name in exclude:
            packages.pop(name.lower(), None)

    _log.info('Updating packages')
    # Update bacpypes with easy_install, because it is only provided as an egg
    requirement = packages.pop('bacpypes', None)
    if requirement:
        easy_install([requirement], verbose, True)
    # Update pip before others to limit upgrade warning message
    requirement = packages.pop('pip', None)
    if requirement:
        pip_install([requirement], verbose, True)
    # Update pyzmq separately to pass install options
    requirement = packages.pop('pyzmq', None)
    if requirement:
        pip_install(['--install-option', '--zmq=bundled', requirement],
                    verbose, True)
    # Update remaining packages
    if packages:
        pip_install(packages.values(), verbose, True)


class HelpFormatter(argparse.HelpFormatter):
    '''Custom formatter to improve -u/--upgrade help.'''
    def _format_action_invocation(self, action):
        if action.dest == 'upgrade':
            return '-u, --upgrade [[!] PKG...]'
        return super(HelpFormatter, self)._format_action_invocation(action)


def main(argv=sys.argv):
    '''Script entry point.'''
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
        usage='\n  bootstrap: python2.7 %(prog)s [OPTIONS]...'
              '\n  update:    {} %(prog)s [OPTIONS]...'.format(python),
        prog=os.path.basename(argv[0]),
        formatter_class=HelpFormatter,
        epilog='''
            The first invocation of this script, which should be made
            using the system, Python, will create a virtual Python
            environment in a subdirectory named 'env' in the same directory
            as this script or in the directory given by the --envdir option.
            Subsequent invocations of this script should use the Python
            executable installed in the virtual environment. If no arguments
            are given with the -u/--upgrade option, all installed packages
            will be upgraded. Packages may be limited, by listing the
            packages that should be updated, or excluded, by including a
            bang (!) as the first item in the list. Some shells may require
            escaping the bang.'''

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
        '--force', action='store_true',
        help='force installing in non-empty directory')
    bs.add_argument(
        '-o', '--only-virtenv', action='store_true',
        help='create virtual environment and exit (skip install)')
    bs.add_argument(
        '--prompt', default='(volttron)', help='provide alternate prompt '
        'in activated environment (default: %(default)s)')
    bs.add_argument('--force-version', help=argparse.SUPPRESS)
    up = parser.add_argument_group('update options')
    up.add_argument(
        '-u', '--upgrade', nargs='*', metavar='PKG',
        help='upgrade installed packages')
    path = os.path.dirname(__file__) or os.getcwd()
    parser.set_defaults(envdir=os.path.join(path, 'env'))
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
        if options.upgrade is not None:
            upgrade(options.upgrade, options.verbose)
        else:
            install(options.verbose)
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
        env_exe = bootstrap_virtenv(options.envdir, options.prompt,
                                    options.force_version, options.verbose)
        if options.only_virtenv:
            return
        # Run this script within the virtual environment for stage2
        args = [env_exe, __file__]
        if options.verbose is not None:
            args.append('--verbose' if options.verbose else '--quiet')
        check_call(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

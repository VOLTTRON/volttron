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

# pylint: disable=W0142,W0403
#}}}

'''Agent packaging and signing support.
'''
import logging
from logging import handlers
import os
import shutil
import subprocess
import sys
import uuid
import wheel
import tempfile

from wheel.install import WheelFile
from .packages import *
from . import config
from .agent import utils

try:
     from volttron.restricted import (auth, certs)
except ImportError:
     auth = None
     certs = None


_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)

DEFAULT_CERTS_DIR = '~/.volttron/certificates'

def log_to_file(file, level=logging.WARNING,
                handler_class=logging.StreamHandler):
    '''Direct log output to a file (or something like one).'''
    handler = handler_class(file)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter(
            '%(asctime)s %(composite_name)s %(levelname)s: %(message)s'))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


class AgentPackageError(Exception):
    '''Raised for errors during packaging, extraction and signing.'''
    pass


def extract_package(wheel_file, install_dir,
                    include_uuid=False, specific_uuid=None):
    '''Extract a wheel file to the specified location.

    If include_uuid is True then a uuid will be generated under the
    passed location directory.

    The agent final directory will be based upon the wheel's data
    directory name in the following formats:

        if include_uuid == True
            install_dir/datadir_name/uuid
        else
            install_dir/datadir_name

    Arguments
        wheel_file     - The wheel file to extract.
        install_dir    - The root directory where to extract the wheel
        include_uuid   - Auto-generates a uuuid under install_dir to
                         place the wheel file data
        specific_uuid  - A specific uuid to use for extracting the agent.

    Returns
        The folder where the wheel was extracted.
    '''
    real_dir = install_dir

    # Only include the uuid if the caller wants it.
    if include_uuid:
        if uuid == None:
            real_dir = os.path.join(real_dir, uuid.uuid4())
        else:
            real_dir = os.path.join(real_dir, uuid)

    if not os.path.isdir(real_dir):
        os.makedirs(real_dir)

    wf = WheelFile(wheel_file)
    namever = wf.parsed_filename.group('namever')
    destination = os.path.join(real_dir, namever)
    sys.stderr.write("Unpacking to: %s\n" % (destination))
    wf.zipfile.extractall(destination)
    wf.zipfile.close()
    return destination


def repackage(directory, dest=None):
    '''Repack an wheel unpacked into the given directory.

    All files in the RECORD files are added back to the wheel, which is
    written in the current working directory if dest is None or in the
    directory given by dest otherwise.
    '''
    try:
        pkg = UnpackedPackage(directory)
    except ValueError as exc:
        raise AgentPackageError(*exc.args)
    return pkg.repack(dest)


def create_package(agent_package_dir, wheelhouse='/tmp/volttron_wheels'):
    '''Creates a packaged whl file from the passed agent_package_dir.

    If the passed directory doesn't exist or there isn't a setup.py file
    the directory then AgentPackageError is raised.

    Parameters
        agent_package_dir - The directory to package in the wheel file.
        signature         - An optional signature file to sign the RECORD file.

    Returns
        string - The full path to the created whl file.
    '''
    if not os.path.isdir(agent_package_dir):
        raise AgentPackageError("Invalid agent package directory specified")
    setup_file_path = os.path.join(agent_package_dir, 'setup.py')
    if os.path.exists(setup_file_path):
        wheel_path = _create_initial_package(agent_package_dir, wheelhouse)
    else:
        raise NotImplementedError("Packaging extracted wheels not available currently")
        wheel_path = None
    return wheel_path


def _create_initial_package(agent_dir_to_package, wheelhouse):
    '''Create an initial whl file from the passed agent_dir_to_package.

    The function produces a wheel from the setup.py file located in
    agent_dir_to_package.

    Parameters:
        agent_dir_to_package - The root directory of the specific agent
                               that is to be packaged.

    Returns The path and file name of the packaged whl file.
    '''
    tmpdir = tempfile.mkdtemp()
    try:
        builddir = os.path.join(tmpdir, 'pkg')
        distdir = os.path.join(builddir, 'dist')
        shutil.copytree(agent_dir_to_package, builddir)
        subprocess.check_call([sys.executable, 'setup.py', '--no-user-cfg',
                               '--quiet', 'bdist_wheel'], cwd=builddir)
        wheel_name = os.listdir(distdir)[0]
        wheel_path = os.path.join(distdir, wheel_name)
        if not os.path.exists(wheelhouse):
            os.makedirs(wheelhouse, 0750)
        wheel_dest = os.path.join(wheelhouse, wheel_name)
        shutil.move(wheel_path, wheel_dest)
        return wheel_dest
    finally:
        shutil.rmtree(tmpdir, True)

def _files_from_kwargs(**kwargs):
    '''Grabs the contract and config file from the kwargs

    Returns None if neither exist.
    '''

    files = {}

    if 'contract' in kwargs and kwargs['contract'] != None:
        files['contract'] = kwargs['contract']
    if 'config_file' in kwargs and kwargs['config_file'] != None:
        files['config_file'] = kwargs['config_file']

    if len(files.keys()) > 0:
        return files

    return None

def _sign_agent_package(agent_package, **kwargs):
    '''Sign an agent package'''
    if not os.path.exists(agent_package):
        raise AgentPackageError('Invalid package {}'.format(agent_package))

    cert_type = _cert_type_from_kwargs(**kwargs)
    files = _files_from_kwargs(**kwargs)
    certs_dir = kwargs.get('certs_dir', None)
    
    certsobj = None
    
    if certs_dir is not None:
        certsobj = certs.Certs(certs_dir)

    if cert_type == 'admin':
        if files:
            raise AgentPackageError("soi's aren't allowed to add files.")
        verified = auth.sign_as_admin(agent_package, 'admin', certsobj = certsobj)
    elif cert_type == 'creator':
        verified = auth.sign_as_creator(agent_package, 'creator', files, certsobj = certsobj)
    elif cert_type == 'initiator':
        verified = auth.sign_as_initiator(agent_package, 'initiator', files, certsobj = certsobj)
    elif cert_type == 'platform':
        verified = auth.sign_as_platform(agent_package, 'platform', files)
    else:
        raise AgentPackageError('Unknown packaging options')

    if verified:
        print('{} signed as {}'.format(agent_package, cert_type))
    else:
        print('Verification of signing failed!')



def _cert_type_from_kwargs(**kwargs):
    '''Return cert type string from kwargs values'''

    for k in ('admin', 'creator', 'initiator', 'platform'):
        try:
            if k in kwargs['user_type'] and kwargs['user_type'][k]:
                return k
        except:
            if k in kwargs and kwargs[k]:
                return k

    return None


def _create_ca(certs_dir=DEFAULT_CERTS_DIR):
    '''Creates a root ca cert using the Certs class'''
    crts = certs.Certs(certs_dir)
    if crts.ca_exists():
        msg = '''Creating a new root ca will overwrite the current ca and
invalidate any signed certs.

Are you sure you want to do this? type 'yes' to continue: '''

        continue_yes = raw_input(msg)
        if continue_yes.upper() != 'YES':
            return

    data = _create_cert_ui(certs.DEFAULT_ROOT_CA_CN)
    crts.create_root_ca(**data)

def _create_cert(name=None, certs_dir= DEFAULT_CERTS_DIR,**kwargs):
    '''Create a cert using options specified on the command line'''

    crts = certs.Certs(certs_dir)
    if not crts.ca_exists():
        sys.stderr.write('Root CA ot must be created before certificates\n')
        sys.exit(0)

    cert_type = _cert_type_from_kwargs(**kwargs)

    if name == None:
        name = cert_type
        cert_data = _create_cert_ui(cert_type)
    else:
        cert_data = _create_cert_ui('{} ({})'.format(cert_type, name))


    crts.create_ca_signed_cert(name, **cert_data)


def _create_cert_ui(cn):
    '''Runs through the different options for the user to create a cert.

        C  - Country
        ST - State
        L  - Location
        O  - Organization
        OU - Organizational Unit
        CN - Common Name
    '''
    input_order = ['C', 'ST', 'L', 'O', 'OU', 'CN']
    input_defaults = {'C':'US',
                      'ST': 'Washington',
                      'L': 'Richland',
                      'O': 'PNNL',
                      'OU': 'Volttron Team',
                      'CN': cn}
    input_help = {'C': 'Country',
                  'ST': 'State',
                  'L': 'Location',
                  'O': 'Organization',
                  'OU': 'Organization Unit',
                  'CN': 'Common Name'}
    output_items = {}
    sys.stdout.write("Please enter the following for certificate creation:\n")
    for item in input_order:
        cmd = '\t{} - {}({}): '.format(item, input_help[item],
                                              input_defaults[item])
        output_items[item] = raw_input(cmd)
        if len(output_items[item].strip()) == 0:
            output_items[item] = input_defaults[item]

    return output_items




def add_files_to_package(package, files=None):

    whl = VolttronPackageWheelFileNoSign(package, append=True)
    whl.add_files(files, whl)


def main(argv=sys.argv):

    expandall = lambda string: os.path.expanduser(os.path.expandvars(string))
    home = expandall(os.environ.get('VOLTTRON_HOME', '~/.volttron'))
    os.environ['VOLTTRON_HOME'] = home

    # Setup option parser
    progname = os.path.basename(argv[0])
    parser = config.ArgumentParser(
        prog=progname,
        description='VOLTTRON packaging and signing utility',
    )
    parser.set_defaults(log_config=None)
    
    parser.add_argument('-l', '--log', metavar='FILE', default=None,
        help='send log output to FILE instead of stderr')
    parser.add_argument('-L', '--log-config', metavar='FILE',
        help='read logging configuration from FILE')
    parser.add_argument('-q', '--quiet', action='add_const', const=10, dest='verboseness',
        help='decrease logger verboseness; may be used multiple times')
    parser.add_argument('-v', '--verbose', action='add_const', const=-10, dest='verboseness',
        help='increase logger verboseness; may be used multiple times')
    parser.add_argument('--verboseness', type=int, metavar='LEVEL',
        default=logging.WARNING,
        help='set logger verboseness')
    
    subparsers = parser.add_subparsers(title = 'subcommands',
                                       description = 'valid subcommands',
                                       help = 'additional help',
                                       dest='subparser_name')
    package_parser = subparsers.add_parser('package',
        help="Create agent package (whl) from a directory or installed agent name.")

    package_parser.add_argument('agent_directory',
        help='Directory for packaging an agent for the first time (requires setup.py file).')

    repackage_parser = subparsers.add_parser('repackage',
                                           help="Creates agent package from a currently installed agent.")
    repackage_parser.add_argument('directory',
        help='Directory where agent is installed')
    repackage_parser.add_argument('--dest',
        help='Directory to place the wheel file')
    repackage_parser.set_defaults(dest=None)
    
    config_parser = subparsers.add_parser('configure',
        help='add a configuration file to an agent package')
    config_parser.add_argument('package', metavar='PACKAGE',
            help='agent package to configure')
    config_parser.add_argument('config_file', metavar='CONFIG',
        help='configuration file to add to wheel.')
    
    

    if auth is not None:
        cert_dir = os.path.expanduser(DEFAULT_CERTS_DIR)
        if not os.path.exists(cert_dir):
            os.makedirs('/'.join((cert_dir, 'certs')))
            os.makedirs('/'.join((cert_dir, 'private')))
        create_ca_cmd = subparsers.add_parser('create_ca')
        create_cert_cmd = subparsers.add_parser('create_cert')
        create_cert_opts = create_cert_cmd.add_mutually_exclusive_group(required=True)
        create_cert_opts.add_argument('--creator', action='store_true',
            help='create a creator cert')
        create_cert_opts.add_argument('--soi', action='store_true',
            help='create an soi administrator cert')
        create_cert_opts.add_argument('--initiator', action='store_true',
            help='create an initiator cert')
        create_cert_opts.add_argument('--platform', action='store_true',
            help='create a platform cert')
        create_cert_cmd.add_argument('--name',
            help='file name to store the cert under (no extension)')

        sign_cmd = subparsers.add_parser('sign',
            help='sign a package')

        sign_opts = sign_cmd.add_mutually_exclusive_group(required=True)
        sign_opts.add_argument('--creator', action='store_true',
            help='sign as the creator of the package')
        sign_opts.add_argument('--soi', action='store_true',
            help='sign as the soi administrator')
        sign_opts.add_argument('--initiator', action='store_true',
            help='sign as the initiator of the package')
        sign_opts.add_argument('--platform', action='store_true',
            help='sign the mutable luggage of the package as the platform')
        sign_cmd.add_argument('--cert', metavar='CERT',
            help='certificate to use to sign the package')
        sign_cmd.add_argument('--config-file', metavar='CONFIG',
            help='agent configuration file')
        sign_cmd.add_argument('--contract', metavar='CONTRACT',
            help='agent resource contract file')
        sign_cmd.add_argument('--certs_dir', metavar='CERTS_DIR',
            help='certificates directory')
        sign_cmd.add_argument('package', metavar='PACKAGE',
            help='agent package to sign')

        #restricted = subparsers.add_parser('sign')
#         restricted.add_argument('package',
#             help='The agent package to sign (whl).')

        verify_cmd = subparsers.add_parser('verify',
            help='verify an agent package')
        verify_cmd.add_argument('package', metavar='PACKAGE',
            help='agent package to verify')

#         enable_restricted_parser = subparsers.add_parser('enable-restricted',
#             help='Enable the restricted features of VOLTTRON')
#
#         creator_key_parser = subparsers.add_parser('set-creator-key',
#             help='Set the key for the creator of the agent code')
#
#         soi_admin_key_parser = subparsers.add_parser('set-SOI-admin-key',
#             help='Set the key for administrator of this Scope of Influence')
#
#         initiator_key_parser = subparsers.add_parser('set-initiator-key',
#             help='Set the key for the initator of this agent')
#
#         source_key_parser = subparsers.add_parser('set-source-key',
#             help='Set the key for the most recent host of this agent')

    opts = parser.parse_args(argv[1:])

    # Configure logging
    level = max(1, opts.verboseness)
    if opts.log is None:
        log_to_file(sys.stderr, level)
    elif opts.log == '-':
        log_to_file(sys.stdout, level)
    elif opts.log:
        log_to_file(opts.log, level, handler_class=handlers.WatchedFileHandler)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())
    if opts.log_config:
        logging.config.fileConfig(opts.log_config)

    # whl_path will be specified if there is a package or repackage command
    # is specified and it was successful.
    whl_path = None
    user_type = None

    try:

        if opts.subparser_name == 'package':
            whl_path = create_package(opts.agent_directory)
        elif opts.subparser_name == 'repackage':
            whl_path = repackage(opts.directory, dest=opts.dest)
        elif opts.subparser_name == 'configure' :
            add_files_to_package(opts.package, {'config_file': opts.config_file})
        else:
            if auth is not None:
                try:
                    if opts.subparser_name == 'create_ca':
                        _create_ca()
                    elif opts.subparser_name == 'verify':
                        if not os.path.exists(opts.package):
                            print('Invalid package name {}'.format(opts.package))
                        verifier = auth.SignedZipPackageVerifier(opts.package)
                        verifier.verify()
                        print "Package is verified"
                    else:
                        user_type = {'admin': opts.soi,
                                  'creator': opts.creator,
                                  'initiator': opts.initiator,
                                  'platform': opts.platform}
                        if opts.subparser_name == 'sign':
                            in_args = {
                                    'config_file': opts.config_file,
                                    'user_type': user_type,
                                    'contract': opts.contract,
                                    'certs_dir': opts.certs_dir
                                }
                            _sign_agent_package(opts.package, **in_args)

                        elif opts.subparser_name == 'create_cert':
                            _create_cert(name=opts.name, **user_type)
                except auth.AuthError as e:
                    _log.error(e.message)
                    #print(e.message)


#         elif opts.subparser_name == 'create_cert':
#             _create_cert(name=opts.name, **)
    except AgentPackageError as e:
        _log.error(e.message)
        #print(e.message)
    except Exception as e:
        _log.error(str(e))
        #print e


    if whl_path:
        print("Package created at: {}".format(whl_path))




def _main():
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    _main()

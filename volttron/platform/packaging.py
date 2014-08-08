'''Agent packaging and signing support.
'''

import hashlib
import logging
import os
import shutil
import sys
import time
import uuid
import wheel

from wheel.install import WheelFile
from wheel.tool import unpack

from volttron.platform import config

try:
    from volttron.restricted import (auth, certs)
except ImportError:
    auth = None
    certs = None

_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)


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


def repackage(agent_name):
    raise AgentPackageError('Repackage is not available')


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
    pwd = os.path.abspath(os.curdir)
    tmp_build_dir = '/tmp/whl_bld'

    unique_str = str(uuid.uuid4())
    tmp_dir = os.path.join(tmp_build_dir, os.path.basename(agent_dir_to_package))
    tmp_dir_unique = tmp_dir + unique_str
    tries = 0

    while os.path.exists(tmp_dir_unique) and tries < 5:
        tmp_dir_unique = tmp_dir + hashlib.sha224(str(time.gmtime())).hexdigest()
        tries += 1
        time.sleep(1)

    shutil.copytree(agent_dir_to_package, tmp_dir_unique)

    distdir = tmp_dir_unique
    os.chdir(distdir)
    wheel_name = None
    try:
        print(distdir)
        sys.argv = ['', 'bdist_wheel']
        exec(compile(open('setup.py').read(), 'setup.py', 'exec'))

        wheel_name = os.listdir('./dist')[0]

        wheel_file_and_path = os.path.join(os.path.abspath('./dist'), wheel_name)
    finally:
        os.chdir(pwd)

    if not os.path.exists(wheelhouse):
        os.makedirs(wheelhouse)

    final_dest = os.path.join(wheelhouse, wheel_name)
#     print("moving {} to {}".format(wheel_file_and_path, final_dest))
#     print("removing {}".format(tmp_dir_unique))
    shutil.move(wheel_file_and_path, final_dest)
    shutil.rmtree(tmp_dir_unique, False)

    return final_dest

def _files_from_kwargs(**kwargs):
    files = []
    if 'contract' in kwargs and kwargs['contract'] != None:
        files.append(kwargs['contract'])
    if 'config_file' in kwargs and kwargs['config_file'] != None:
        files.append(kwargs['config_file'])

    return files

def _sign_agent_package(agent_package, **kwargs):
    '''Sign an agent package'''
    if not os.path.exists(agent_package):
        raise AgentPackageError('Invalid package {}'.format(agent_package))

    cert_type = _cert_type_from_kwargs(**kwargs)
    files = _files_from_kwargs(**kwargs)

    if cert_type == 'soi':
        if files:
            raise AgentPackageError("soi's aren't allowd to add files.")
        verified = auth.sign_as_admin(agent_package, 'soi')
    elif cert_type == 'creator':
        verified = auth.sign_as_creator(agent_package, 'creator', files)
    elif cert_type == 'initiator':
        verified = auth.sign_as_initiator(agent_package, 'initiator', files)
    else:
        raise AgentPackageError('Unknown packaging options')

    if verified:
        print('{} signed as {}'.format(agent_package, cert_type))
    else:
        print('Verification of signing failed!')



def _cert_type_from_kwargs(**kwargs):
    '''Return cert type string from kwargs values'''

    for k in ('soi', 'creator', 'initiator'):
        try:
            if k in kwargs['user_type'] and kwargs['user_type'][k]:
                return k
        except:
            if k in kwargs and kwargs[k]:
                return k

    return None


def _create_ca():
    '''Creates a root ca cert using the Certs class'''
    crts = certs.Certs('~/.volttron/certificates')
    if crts.ca_exists():
        msg = '''Creating a new root ca will overwrite the current ca and
invalidate any signed certs.

Are you sure you want to do this? type 'yes' to continue: '''

        continue_yes = raw_input(msg)
        if continue_yes.upper() != 'YES':
            return

    data = _create_cert_ui(certs.DEFAULT_ROOT_CA_CN)
    crts.create_root_ca(**data)

def _create_cert(name=None, **kwargs):
    '''Create a cert using options specified on the command line'''

    crts = certs.Certs('~/.volttron/certificates')
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






def main(argv=sys.argv):

    expandall = lambda string: os.path.expandvars(os.path.expanduser(string))
    home = expandall(os.environ.get('VOLTTRON_HOME', '~/.volttron'))
    os.environ['VOLTTRON_HOME'] = home

    # Setup option parser
    progname = os.path.basename(argv[0])
    parser = config.ArgumentParser(
        prog=progname,
        description='VOLTTRON packaging and signing utility',
    )
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

    repackage_parser.add_argument('agent_name',
                                help='The name of a currently installed agent.')

    if auth is not None:
        cert_dir = os.path.expanduser('~/.volttron/certificates')
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
        sign_cmd.add_argument('--cert', metavar='CERT',
            help='certificate to use to sign the package')
        sign_cmd.add_argument('--config-file', metavar='CONFIG',
            help='agent configuration file')
        sign_cmd.add_argument('--contract', metavar='CONTRACT',
            help='agent resource contract file')
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

    args = parser.parse_args(argv[1:])

    # whl_path will be specified if there is a package or repackage command
    # is specified and it was successful.
    whl_path = None
    user_type = None

    try:

        if args.subparser_name == 'package':
            whl_path = create_package(args.agent_directory)
        elif args.subparser_name == 'repackage':
            whl_path = repackage(args.agent_name)
        else:
            if auth is not None:
                try:
                    if args.subparser_name == 'create_ca':
                        _create_ca()
                    elif args.subparser_name == 'verify':
                        if not os.path.exists(args.package):
                            print('Invalid package name {}'.format(args.package))
                        verifier = auth.ZipPackageVerifier(args.package)
                        verifier.verify()
                        print "Package is verified"
                    else:
                        user_type = {'soi': args.soi,
                                  'creator': args.creator,
                                  'initiator': args.initiator}
                        if args.subparser_name == 'sign':
                            in_args = {
                                    'config_file': args.config_file,
                                    'user_type': user_type,
                                    'contract': args.contract,
                                }

                            result = _sign_agent_package(args.package, **in_args)

                        elif args.subparser_name == 'create_cert':
                            _create_cert(name=args.name, **user_type)
                except auth.AuthError as e:
                    print(e.message)


#         elif args.subparser_name == 'create_cert':
#             _create_cert(name=args.name, **)
    except AgentPackageError as e:
        print(e.message)
    except auth.AuthError as e:
        print(e.message)


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

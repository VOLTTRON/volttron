'''Agent packaging and signing support.
'''
import base64
from collections import Iterable
from contextlib import closing
import csv
import errno
import hashlib
import logging
import os
import posixpath
import re
import shutil
import StringIO
import sys
import time
import uuid
import wheel
import tempfile
import zipfile

try:
    import simplejson as jsonapi
except ImportError:
    import json as jsonapi

from wheel.install import WheelFile
from wheel.tool import unpack
from wheel.util import (native,
                        open_for_csv,
                        urlsafe_b64decode)
from volttron.platform.packages import (BasePackageVerifier, VolttronPackageWheelFileNoSign, ZipPackageVerifier)
from volttron.platform import config

from volttron.restricted import (auth, certs)

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


def repackage(directory, dest=None):
    '''Repack an wheel unpacked into the given directory.

    All files in the RECORD files are added back to the wheel, which is
    written in the current working directory if dest is None or in the
    directory given by dest otherwise.
    '''
    for name in os.listdir(directory):
        if not name.endswith('.dist-info'):
            continue
        distinfo = os.path.join(directory, name)
        try:
            with open(os.path.join(distinfo, 'metadata.json')) as file:
                metadata = jsonapi.load(file)
            with open(os.path.join(distinfo, 'WHEEL')) as file:
                wheel = {key.strip().lower(): value.strip()
                         for key, value in
                         (parts for line in file if line
                          for parts in [line.split(':', 1)] if len(parts) == 2)}
        except EnvironmentError as exc:
            if exc.errno == errno.ENOENT:
                continue
            raise
        try:
            metadata['tag'] = wheel['tag']
            pkgname = '{name}-{version}-{tag}'.format(**metadata)
        except KeyError:
            continue
        if not pkgname.startswith(name[:-10] + '-'):
            continue
        break
    else:
        raise AgentPackageError('directory does not appear to contain a '
                                'valid agent package')

    regex = re.compile(r'^RECORD(?:\.\d+)?$')
    records = [name for name in os.listdir(distinfo) if regex.match(name)]
    records.sort()
    wheelname = pkgname + '.whl'
    if dest is not None:
        dest = os.path.expanduser(os.path.expandvars(dest))
        wheelname = os.path.join(dest, wheelname)
    with zipfile.ZipFile(wheelname, 'w') as wheelfile:
        try:
            for record in records:
                with open(os.path.join(distinfo, record)) as file:
                    csvfile = csv.reader(file)
                    for row in csvfile:
                        name = row[0]
                        wheelfile.write(os.path.join(directory, name), name)
        except Exception:
            wheelfile.close()
            os.unlink(wheelfile.filename)
            raise
    return wheelfile.filename

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

    if cert_type == 'soi':
        if files:
            raise AgentPackageError("soi's aren't allowed to add files.")
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
            whl_path = repackage(args.directory, dest=args.dest)
        elif args.subparser_name == 'configure' :
            add_files_to_package(args.package, {'config_file': args.config_file})
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
                            _sign_agent_package(args.package, **in_args)

                        elif args.subparser_name == 'create_cert':
                            _create_cert(name=args.name, **user_type)
                except auth.AuthError as e:
                    print(e.message)


#         elif args.subparser_name == 'create_cert':
#             _create_cert(name=args.name, **)
    except AgentPackageError as e:
        print(e.message)
    except Exception as e:
        print e


    if whl_path:
        print("Package created at: {}".format(whl_path))


#
# Signature verification in the class below has the limitation that only
# a single certificate may be used for verification. Ideally, the
# certificate should be extracted from the signature file and verified
# against a certificate authority (CA) in the CA store. See
# http://code.activestate.com/recipes/285211/ for an alternate solution
# using M2Crypto.
#
class BasePackageVerifier(object):
    '''Base class for implementing wheel package verification.

    Verifies wheel packages as defined in PEP-427. May be inherited with
    minimal modifications to support different storage mechanisms, such
    as a filesystem, Zip file, or tarball. All paths are expected to be
    POSIX-style with forward-slashes. Subclasses should implement
    listdir and open and may override __init__, if needed.

    As an extension of the original specification, multiple levels of
    RECORD files and signatures are supported by appending incrementing
    integers to the RECORD files. Verification happens in reverse order
    and later RECORD files should contain hashes of the previous RECORD
    and associated signature file(s).
    '''

    _record_re = re.compile(r'^RECORD(?:\.\d+)?$')

    def __init__(self, dist_info, digest='sha256', **kwargs):
        '''Initialize the instance with the dist-info directory name.

        dist_info should contain the name of a single directory, not a
        multi-component path.
        '''
        self.dist_info = dist_info
        self.digest = digest

       

    def listdir(self, path):
        '''Return a possibly empty list of files from a directory.

        This could return the contents of a directory in an archive or
        whatever makes sense for the storage mechanism. Paths will
        typically be relative to the package, however, for installed
        packages, absolute paths are possible.
        '''
        raise NotImplementedError()

    def open(self, path, mode='r'):
        '''Return a file-like object for the given file.

        mode is interpreted the same as for the built-in open and will
        be either 'r' or 'rb'. Only the __iter__(), read(), and close()
        methods are used.
        '''
        raise NotImplementedError()

    def iter_hashes(self, name='RECORD'):
        '''Iterate over the files and hashes of a RECORD file.

        The RECORD file with the given name will be iterated over
        yielding a three tuple with each iteration: filename (relative
        to the package), computed hash (just calculated), and expected
        hash (from RECORD file).
        '''
        hashless = [posixpath.join(self.dist_info, name + ext)
                    for ext in ['', '.jws', '.p7s']]
        path = posixpath.join(self.dist_info, name)
        with closing(self.open(path)) as record_file:
            for row in csv.reader(record_file):
                filename, hashspec = row[:2]
                if not hashspec:
                    if filename not in hashless:
                        yield filename, None, None
                    continue
                algo, expected_hash = hashspec.split('=', 1)
                hash = hashlib.new(algo)
                with closing(self.open(filename, 'rb')) as file:
                    while True:
                        data = file.read(4096)
                        if not data:
                            break
                        hash.update(data)
                hash = base64.urlsafe_b64encode(hash.digest()).rstrip('=')
                yield filename, hash, expected_hash

    def get_records(self):
        '''Return a reverse sorted list of RECORD names from the package.

        Returns all RECORD files in the dist_info directory.
        '''
        records = [name for name in self.listdir(self.dist_info)
                   if self._record_re.match(name)]
        records.sort(key=lambda x: int((x.split('.', 1) + [-1])[1]), reverse=True)
        if not records:
            raise ValueError('missing RECORD file(s) in .dist-info directory')
        return records



def _main():
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    _main()

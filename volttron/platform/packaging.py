# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

"""Agent packaging and signing support.
"""
import logging
from logging import handlers
import os
import shutil
import subprocess
import sys
import uuid
import tempfile
import traceback
import errno

from wheel.install import WheelFile
from volttron.platform.packages import *
from volttron.platform.agent import utils
from volttron.platform import get_volttron_data, get_home
from volttron.utils.prompt import prompt_response
from volttron.platform import certs
from volttron.platform import config

try:
     from volttron.restricted import auth
except ImportError:
     auth = None


_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)

AGENT_TEMPLATE_PATH_TEMPLATE = "agent_templates/{name}/{file}"
AGENT_TEMPLATE_PATH = "agent_templates/"
AGENT_TEMPLATE_SETUP = "agent_templates/setup.py_"


def log_to_file(file, level=logging.WARNING,
                handler_class=logging.StreamHandler):
    """Direct log output to a file (or something like one)."""
    handler = handler_class(file)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter(
            '%(asctime)s %(composite_name)s %(levelname)s: %(message)s'))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


class AgentPackageError(Exception):
    """Raised for errors during packaging, extraction and signing."""
    pass


def _get_agent_template_list():
    data_root = get_volttron_data()
    template_path = os.path.join(data_root, AGENT_TEMPLATE_PATH)
    return [o for o in os.listdir(template_path)
            if os.path.isdir(os.path.join(template_path,o))]


def _load_agent_template(template_name):
    data_root = get_volttron_data()
    setup_path = os.path.join(data_root, AGENT_TEMPLATE_SETUP)
    agent_path = os.path.join(data_root, AGENT_TEMPLATE_PATH_TEMPLATE.format(name=template_name,
                                                                             file="agent.py_"))
    config_path = os.path.join(data_root, AGENT_TEMPLATE_PATH_TEMPLATE.format(name=template_name,
                                                                                file="config"))

    setup_template = None
    agent_template = None
    config_template = None

    try:
        with open(setup_path) as f:
            setup_template = f.read()

        with open(agent_path) as f:
            agent_template = f.read()

        with open(config_path) as f:
            config_template = f.read()
    except IOError as e:
        _log.error("Error loading template: {}".format(str(e)))
        sys.exit(1)

    return setup_template, agent_template, config_template


def _get_agent_metadata(silent):
    results = {
        "version": "0.1",
        "author": None,
        "author_email": None,
        "url": None,
        "description": None
    }

    if silent:
        return results

    results["version"] =        prompt_response("Agent version number:", default="0.1")
    results["author"] =         prompt_response("Agent author:", default="")
    results["author_email"] =   prompt_response("Author's email address:", default="")
    results["url"] =            prompt_response("Agent homepage:", default="")
    results["description"] =    prompt_response("Short description of the agent:", default="")

    return results


def _get_setup_py(template, agent_package, metadata):
    metadata_strings = []

    for key, value in metadata.items():
        if value:
            metadata_strings.append('{key}="{value}",'.format(key=key, value=value))

    metadata_string = "\n    ".join(metadata_strings)

    template = template.replace("__package_name__", agent_package)
    template = template.replace("__meta_data__", metadata_string)

    return template


def _get_agent_py(template, module_name, class_name, version, agent_id):
    template = template.replace("__version_string__", version)
    template = template.replace("__module_name__", module_name)
    template = template.replace("__class_name__", class_name)

    if agent_id is not None:
        template = template.replace("__identity__", 'identity="'+agent_id+'",')
    else:
        template = template.replace("__identity__", "")

    return template


def _to_camel_case(input):
    parts = input.split('_')
    return "".join(x.title() for x in parts)


def init_agent(target_directory, module_name, template_name, silent, identity):
    setup_template, agent_template, config_string = _load_agent_template(template_name)
    metadata = _get_agent_metadata(silent)

    version = metadata.pop("version")

    setup_string = _get_setup_py(setup_template, module_name, metadata)

    class_name = _to_camel_case(module_name)

    agent_string = _get_agent_py(agent_template, module_name, class_name, version, identity)

    try:
        _log.info("Creating {}".format(target_directory))
        os.makedirs(target_directory)
        module_dir = os.path.join(target_directory, module_name)
        _log.info("Creating {}".format(module_dir))
        os.makedirs(module_dir)
    except OSError as e:
        if e.errno == errno.EEXIST:
            _log.error("Must specify a new directory name to create agent.")
        else:
            _log.error("Unable to create target directory: "+str(e))
        sys.exit(1)

    try:
        setup_path = os.path.join(target_directory, "setup.py")
        _log.info("Creating {}".format(setup_path))
        with open(setup_path, "w")as f:
            f.write(setup_string)

        config_path = os.path.join(target_directory, "config")
        _log.info("Creating {}".format(config_path))
        with open(config_path, "w")as f:
            f.write(config_string)

        agent_path = os.path.join(target_directory, module_name, "agent.py")
        _log.info("Creating {}".format(agent_path))
        with open(agent_path, "w")as f:
            f.write(agent_string)

        init_path = os.path.join(target_directory, module_name, "__init__.py")
        _log.info("Creating {}".format(init_path))
        with open(init_path, "w")as f:
            pass

        if identity is not None:
            identity_path = os.path.join(target_directory, "IDENTITY")
            _log.info("Creating {}".format(identity_path))
            with open(identity_path, "w")as f:
                f.write(identity)

    except OSError as e:
        _log.error("Unable to create agent file: " + str(e))
        sys.exit(1)


def extract_package(wheel_file, install_dir,
                    include_uuid=False, specific_uuid=None):

    """
    Extract a wheel file to the specified location.

    If include_uuid is True then a uuid will be generated under the
    passed location directory.

    The agent final directory will be based upon the wheel's data
    directory name in the following formats:

    .. code-block:: python

        if include_uuid == True
            install_dir/uuid/datadir_name
        else
            install_dir/datadir_name

    :param wheel_file: The wheel file to extract.
    :param install_dir: The root directory where to extract the wheel
    :param include_uuid: Auto-generates a uuuid under install_dir to place the
                         wheel file data
    :param specific_uuid: A specific uuid to use for extracting the agent.
    :return: The folder where the wheel was extracted.

    """
    real_dir = install_dir

    # Only include the uuid if the caller wants it.
    if include_uuid:
        if specific_uuid == None:
            real_dir = os.path.join(real_dir, str(uuid.uuid4()))
        else:
            real_dir = os.path.join(real_dir, specific_uuid)

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
    """Repack an wheel unpacked into the given directory.

    All files in the RECORD files are added back to the wheel, which is
    written in the current working directory if dest is None or in the
    directory given by dest otherwise.
    """
    if dest is not None:
        try:
            if not os.path.isdir(dest):
                os.makedirs(dest)
        except Exception as e:
            raise AgentPackageError("Unable to create destination directory "
                                    "{}. Exception {}".format(
                                    dest, e.args[0]))
    if not os.path.exists(directory):
        raise AgentPackageError("Agent directory {} does not "
                                "exist".format(directory))
    try:
        pkg = UnpackedPackage(directory)
    except ValueError as exc:
        raise AgentPackageError(*exc.args)
    return pkg.repack(dest)


# default_wheel_dir = os.environ['VOLTTRON_HOME']+'/packaged'
def create_package(agent_package_dir, wheelhouse, identity=None):
    """Creates a packaged whl file from the passed agent_package_dir.

    If the passed directory doesn't exist or there isn't a setup.py file
    the directory then AgentPackageError is raised.

    Parameters
        agent_package_dir - The directory to package in the wheel file.
        signature         - An optional signature file to sign the RECORD file.

    Returns
        string - The full path to the created whl file.
    """
    if not os.path.isdir(agent_package_dir):
        raise AgentPackageError("Invalid agent package directory specified")
    setup_file_path = os.path.join(agent_package_dir, 'setup.py')
    if os.path.exists(setup_file_path):
        wheel_path = _create_initial_package(agent_package_dir, wheelhouse, identity)
    else:
        raise NotImplementedError("Packaging extracted wheels not available currently")
        wheel_path = None
    return wheel_path


def _create_initial_package(agent_dir_to_package, wheelhouse, identity=None):
    """Create an initial whl file from the passed agent_dir_to_package.

    The function produces a wheel from the setup.py file located in
    agent_dir_to_package.

    Parameters:
        agent_dir_to_package - The root directory of the specific agent
                               that is to be packaged.

    Returns The path and file name of the packaged whl file.
    """
    try:
        tmpdir = tempfile.mkdtemp()

        builddir = os.path.join(tmpdir, 'pkg')
        distdir = os.path.join(builddir, 'dist')
        shutil.copytree(agent_dir_to_package, builddir)
        cmd = [sys.executable, 'setup.py', '--no-user-cfg', 'bdist_wheel']
        response = subprocess.run(cmd, cwd=builddir, stderr=subprocess.PIPE,
                                  stdout=subprocess.PIPE)
        if response.returncode != 0:
            raise ValueError(f"Couldn't compile agent directory: {response.stderr}")

        wheel_name = os.listdir(distdir)[0]
        wheel_path = os.path.join(distdir, wheel_name)

        if identity is not None:
            tmp_identity_file_fd, identity_template_filename = tempfile.mkstemp(dir=builddir)
            tmp_identity_file = os.fdopen(tmp_identity_file_fd, "w")
            tmp_identity_file.write(identity)
            tmp_identity_file.close()
        else:
            identity_template_filename = os.path.join(builddir, "IDENTITY")

        if os.path.exists(identity_template_filename):
            add_files_to_package(wheel_path, {'identity_file': identity_template_filename})

        if not os.path.exists(wheelhouse):
            os.makedirs(wheelhouse, 0o750)
        wheel_dest = os.path.join(wheelhouse, wheel_name)
        shutil.move(wheel_path, wheel_dest)
        return wheel_dest
    except subprocess.CalledProcessError as ex:
        traceback.print_last()
        raise ex
    finally:
        shutil.rmtree(tmpdir, True)


def _files_from_kwargs(**kwargs):
    """Grabs the contract and config file from the kwargs

    Returns None if neither exist.
    """

    files = {}

    if 'contract' in kwargs and kwargs['contract'] != None:
        files['contract'] = kwargs['contract']
    if 'config_file' in kwargs and kwargs['config_file'] != None:
        files['config_file'] = kwargs['config_file']

    if len(files) > 0:
        return files

    return None


def _sign_agent_package(agent_package, **kwargs):
    """Sign an agent package"""
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
            raise AgentPackageError("admin's aren't allowed to add files.")
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
        print('f{agent_package} signed as {cert_type}')
    else:
        print('Verification of signing failed!')


def _cert_type_from_kwargs(**kwargs):
    """Return cert type string from kwargs values"""

    for k in ('admin', 'creator', 'initiator', 'platform'):
        try:
            if k in kwargs['user_type'] and kwargs['user_type'][k]:
                return k
        except LookupError:
            if k in kwargs and kwargs[k]:
                return k

    return None


def _create_ca(override=True, data=None):
    """Creates a root ca cert using the Certs class"""
    crts = certs.Certs()
    if crts.ca_exists():
        if override:
            msg = '''Creating a new root ca will overwrite the current ca and
    invalidate any signed certs.
    
    Are you sure you want to do this? type 'yes' to continue: '''

        continue_yes = input(msg)
        if continue_yes.upper() != 'YES':
            return
    if not data:
        data = _create_cert_ui(crts.default_root_ca_cn)
    crts.create_root_ca(**data)


def _create_cert(name=None, **kwargs):
    """Create a cert using options specified on the command line"""

    crts = certs.Certs()
    if not crts.ca_exists():
        sys.stderr.write('Root CA must be created before certificates\n')
        sys.exit(0)

    cert_type = _cert_type_from_kwargs(**kwargs)

    if name == None:
        name = cert_type
        cert_data = _create_cert_ui(cert_type)
    else:
        cert_data = _create_cert_ui('{} ({})'.format(cert_type, name))

    crts.create_signed_cert_files(name, **cert_data)


def _create_cert_ui(cn):
    """Runs through the different options for the user to create a cert.

        C  - Country
        ST - State
        L  - Location
        O  - Organization
        OU - Organizational Unit
        CN - Common Name
    """
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
    # TODO Add country code verification. cryptography package doesn't do it
    for item in input_order:
        cmd = '\t{} - {}({}): '.format(item, input_help[item],
                                              input_defaults[item])
        output_items[item] = input(cmd)
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
    default_wheelhouse = os.environ['VOLTTRON_HOME']+'/packaged'

    # Setup option parser
    progname = os.path.basename(argv[0])
    parser = config.ArgumentParser(
        prog=progname,
        description='VOLTTRON packaging and signing utility',
    )
    parser.set_defaults(log_config=None, verboseness=logging.INFO)

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
                                           help="Create agent package (whl) from a directory")

    package_parser.add_argument('agent_directory',
                                help='Directory for packaging an agent for the first time (requires setup.py file).')
    package_parser.add_argument('--dest',
                                help='Directory to place the wheel file')
    package_parser.set_defaults(dest=default_wheelhouse)
    package_parser.add_argument('--vip-identity',
                                help='Override the Agents desired VIP IDENTITY (if any). '
                                     'Takes precedent over default VIP IDENTITY generated by '
                                     'the platform and the preferred identity of the agent (if any).')
    package_parser.set_defaults(identity=None)

    init_parser = subparsers.add_parser('init',
                                        help="Create new agent code package from a template."
                                             " Will prompt for additional metadata.")

    init_parser.add_argument('directory',
                             help='Directory to create the new agent in (must not exist).')
    init_parser.add_argument('module_name',
                             help='Module name for agent. Class name is derived from this name.')
    init_parser.add_argument('--template', choices=_get_agent_template_list(),
                             help='Name of the template to use. Defaults to "common".')
    init_parser.add_argument('--identity',
                             help='Set agent to have a fixed VIP identity. Useful for new service agents.')
    init_parser.add_argument('--silent', action="store_true",
                             help='Use defaults for meta data and do not prompt.')
    init_parser.set_defaults(identity=None, template="common")

    repackage_parser = subparsers.add_parser('repackage',
                                             help="Creates agent package from a currently installed agent.")
    repackage_parser.add_argument('directory',
                                  help='Directory where agent is installed')
    repackage_parser.add_argument('--dest',
                                  help='Directory to place the wheel file')
    repackage_parser.set_defaults(dest=default_wheelhouse)

    config_parser = subparsers.add_parser('configure',
                                          help='add a configuration file to an agent package')
    config_parser.add_argument('package', metavar='PACKAGE',
                               help='agent package to configure')
    config_parser.add_argument('config_file', metavar='CONFIG',
                               help='configuration file to add to wheel.')

    create_ca_cmd = subparsers.add_parser('create_ca')

    if auth is not None:
        create_cert_cmd = subparsers.add_parser('create_cert')
        create_cert_opts = create_cert_cmd.add_mutually_exclusive_group(required=True)
        create_cert_opts.add_argument('--creator', action='store_true',
                                      help='create a creator cert')
        create_cert_opts.add_argument('--admin', action='store_true',
                                      help='create an admin administrator cert')
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
        sign_opts.add_argument('--admin', action='store_true',
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

        verify_cmd = subparsers.add_parser('verify',
                                           help='verify an agent package')
        verify_cmd.add_argument('package', metavar='PACKAGE',
                                help='agent package to verify')

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
            whl_path = create_package(opts.agent_directory, wheelhouse=opts.dest, identity=opts.vip_identity)
        elif opts.subparser_name == 'repackage':
            whl_path = repackage(opts.directory, dest=opts.dest)
        elif opts.subparser_name == 'configure' :
            add_files_to_package(opts.package, {'config_file': opts.config_file})
        elif opts.subparser_name == 'init' :
            init_agent(opts.directory, opts.module_name, opts.template, opts.silent, opts.identity)
        elif opts.subparser_name == 'create_ca':
            _create_ca()
        else:
            if auth is not None:
                try:
                    if opts.subparser_name == 'verify':
                        if not os.path.exists(opts.package):
                            print(f'Invalid package name {opts.package}')
                        verifier = auth.SignedZipPackageVerifier(opts.package)
                        verifier.verify()
                        print("Package is verified")
                    else:
                        user_type = {'admin': opts.admin,
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

    except AgentPackageError as e:
        print(e)

    except Exception as e:
        _log.exception(e)

    if whl_path:
        print(f"Package created at: {whl_path}")


def _main():
    """Entry point for scripts."""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    _main()

import logging
import subprocess
from collections import namedtuple
from pathlib import Path
from typing import List
from typing import Union
from volttron.platform.agent.utils import execute_command

PathStr = Union[Path, str]

__all__ = ['TLSRepository']

_log = logging.getLogger(__name__)

def execute_command2(cmds, env=None, cwd=None, logger=None, err_prefix=None) -> str:
    """ Executes a command as a subprocess, allows for piping
    If the return code of the call is 0 then return stdout otherwise
    raise a RuntimeError.  If logger is specified then write the exception
    to the logger otherwise this call will remain silent.
    :param cmds:list of commands to pass to subprocess.run
    :param env: environment to run the command with
    :param cwd: working directory for the command
    :param logger: a logger to use if errors occure
    :param err_prefix: an error prefix to allow better tracing through the error message
    :return: stdout string if successful
    :raises RuntimeError: if the return code is not 0 from suprocess.run
    """

    results = subprocess.run(cmds, env=env, cwd=cwd,
                             stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    if results.returncode != 0:
        err_prefix = err_prefix if err_prefix is not None else "Error executing command"
        err_message = "\n{}: Below Command failed with non zero exit code.\n" \
                      "Command:{} \nStderr:\n{}\n".format(err_prefix,
                                                          results.args,
                                                          results.stderr)
        if logger:
            logger.exception(err_message)
            raise RuntimeError()
        else:
            raise RuntimeError(err_message)

    return results.stdout.decode('utf-8')

def execute_command(cmds, env=None, cwd=None, logger=None, err_prefix=None) -> str:
    """ Executes a command as a subprocess
    If the return code of the call is 0 then return stdout otherwise
    raise a RuntimeError.  If logger is specified then write the exception
    to the logger otherwise this call will remain silent.
    :param cmds:list of commands to pass to subprocess.run
    :param env: environment to run the command with
    :param cwd: working directory for the command
    :param logger: a logger to use if errors occure
    :param err_prefix: an error prefix to allow better tracing through the error message
    :return: stdout string if successful
    :raises RuntimeError: if the return code is not 0 from suprocess.run
    """

    results = subprocess.run(cmds, env=env, cwd=cwd,
                             stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if results.returncode != 0:
        err_prefix = err_prefix if err_prefix is not None else "Error executing command"
        err_message = "\n{}: Below Command failed with non zero exit code.\n" \
                      "Command:{} \nStderr:\n{}\n".format(err_prefix,
                                                          results.args,
                                                          results.stderr)
        if logger:
            logger.exception(err_message)
            raise RuntimeError()
        else:
            raise RuntimeError(err_message)

    return results.stdout.decode('utf-8')


class TLSRepository:

    def __init__(self, repo_dir: PathStr, openssl_cnffile: PathStr, serverhost: str, clear=False):
        if isinstance(repo_dir, str):
            repo_dir = Path(repo_dir).expanduser().resolve()
        if isinstance(openssl_cnffile, str):
            openssl_cnffile = Path(openssl_cnffile).expanduser().resolve()
            if not openssl_cnffile.exists():
                raise ValueError(f"openssl_cnffile does not exist {openssl_cnffile}")
        self._repo_dir = repo_dir
        self._certs_dir = repo_dir.joinpath("certs")
        self._private_dir = repo_dir.joinpath("private")
        self._openssl_cnf_file = self._repo_dir.joinpath(openssl_cnffile.name)
        self._hostnames = {serverhost: serverhost}

        if not self._repo_dir.exists() or not self._certs_dir.exists() or \
                not self._private_dir.exists():
            self._certs_dir.mkdir(parents=True)
            self._private_dir.mkdir(parents=True)

        index_txt = self._repo_dir.joinpath("index.txt")
        serial = self._repo_dir.joinpath("serial")
        if clear:
            for x in self._private_dir.iterdir():
                x.unlink()
            for x in self._certs_dir.iterdir():
                x.unlink()
            for x in self._repo_dir.iterdir():
                if x.is_file():
                    x.unlink()
            try:
                index_txt.unlink()
            except FileNotFoundError:
                pass
            try:
                serial.unlink()
            except FileNotFoundError:
                pass

        if not index_txt.exists():
            index_txt.write_text("")
        if not serial.exists():
            serial.write_text("01")

        new_contents = openssl_cnffile.read_text().replace("dir             = /home/gridappsd/tls",
                                                           f"dir = {repo_dir}")
        self._openssl_cnf_file.write_text(new_contents)
        self._ca_key = self._private_dir.joinpath("VC-root-ca.pem")
        self._ca_cert = self._certs_dir.joinpath("VC-root-ca.crt")
        self._serverhost = serverhost

        # Create a new ca key if not exists.
        if not Path(self._ca_key).exists():
            self.__create_ca__()
            __openssl_create_private_key__(self.__get_key_file__(self._serverhost))
            self.create_cert(self._serverhost, True)

    def __create_ca__(self):
        __openssl_create_private_key__(self._ca_key)
        #__openssl_create_ca_certificate__("ca", self._ca_key, self._ca_cert)
        __openssl_create_ca_certificate__("VC-root-ca", self._ca_key, self._ca_cert)

    def create_cert(self, hostname: str, as_server: bool = False):
        if not self.__get_key_file__(hostname).exists():
            __openssl_create_private_key__(self.__get_key_file__(hostname))
        __openssl_create_signed_certificate__(hostname, self._openssl_cnf_file, self._ca_key, self._ca_cert,
                                              self.__get_key_file__(hostname), self.__get_cert_file__(hostname),
                                              as_server)
        self._hostnames[hostname] = hostname

    def fingerprint(self, hostname: str, without_colan: bool = True):
        value = __openssl_fingerprint__(self.__get_cert_file__(hostname))
        if without_colan:
            value = value.replace(":", "")
        return value
    
    def create_csr(self, hostname: str, opensslcnf: Path, private_key_file: Path, csr_file: Path):
        csr = __openssl_create_csr__(hostname, opensslcnf, private_key_file, csr_file)
        return csr

    def verify_csr(self, csr_file_path: str, private_key_file: str):
        return __openssl_verify_csr__(csr_file_path, private_key_file)

    def verify_ca_cert(self, private_key_file: str, ca_cert_file: str):
        return __verify_ca_certificate__(private_key_file, ca_cert_file)

    @property
    def client_list(self) -> List[str]:
        return list(self._hostnames.keys())

    @property
    def ca_key_file(self) -> Path:
        return self._ca_key

    @property
    def ca_cert_file(self) -> Path:
        return self._ca_cert

    @property
    def server_key_file(self) -> Path:
        return self.__get_key_file__(self._serverhost)

    @property
    def server_cert_file(self) -> Path:
        return self.__get_cert_file__(self._serverhost)

    def __get_cert_file__(self, hostname: str) -> Path:
        return self._certs_dir.joinpath(f"{hostname}.crt")

    def __get_key_file__(self, hostname: str) -> Path:
        return self._private_dir.joinpath(f"{hostname}.pem")


def __openssl_create_private_key__(file_path: Path):
    # openssl ecparam -out private/ec-cakey.pem -name prime256v1 -genkey
    cmd = ["openssl", "ecparam", "-out", str(file_path), "-name", "prime256v1", "-genkey"]
    return execute_command(cmd)


def __openssl_create_ca_certificate__(common_name: str, private_key_file: Path, ca_cert_file: Path):
    # openssl req -new -x509 -days 3650 -config openssl.cnf \
    #   -extensions v3_ca -key private/ec-cakey.pem -out certs/ec-cacert.pem
    cmd = ["openssl", "req", "-new", "-x509",
           "-days", "3650",
           "-subj", f"/C=US/CN={common_name}",
           "-extensions", "v3_ca",
           "-key", str(private_key_file),
           "-out", str(ca_cert_file)]
    return execute_command(cmd)


def __verify_ca_certificate__(private_key_file: str, ca_cert_file: str):
    #openssl verify -verbose -CAfile cacert.pem  server.crt
    # openssl x509 -noout -modulus -in server.crt| openssl md5
    # openssl rsa -noout -modulus -in server.key| openssl md5
    cmd = ["openssl", "x509", "-noout", "-modulus", "-in", ca_cert_file, "|", "openssl", "md5"]
    cert_md5 = execute_command2(cmd)
    cmd = ["openssl", "rsa", "-noout", "-modulus", "-in", private_key_file, "|", "openssl", "md5"]
    key_md5 = execute_command2(cmd)
    return cert_md5 == key_md5
    # cmd = ["openssl", "verify", "-verbose", "-CAfile", private_key_file, ca_cert_file]
    # return execute_command(cmd)


def __openssl_create_csr__(common_name: str, opensslcnf: Path, private_key_file: Path, server_csr_file: Path):
    # openssl req -new -key server.key -out server.csr -sha256
    cmd = ["openssl", "req", "-new",
        "-config", str(opensslcnf),
        "-subj", f"/C=US/CN={common_name}",
        "-key", str(private_key_file),
        "-out", str(server_csr_file),
        "-sha256"]
    return execute_command(cmd)


def __openssl_verify_csr__(csr_file_path: str, private_key_file: str):
    cmd = ["openssl", "req", "-text", "-noout", "-verify", "-in", csr_file_path, "-key", private_key_file]
    return execute_command(cmd)


def __openssl_create_signed_certificate__(common_name: str, opensslcnf: Path, ca_key_file: Path, ca_cert_file: Path,
                                          private_key_file: Path, cert_file: Path, as_server: bool = False):
    csr_file = Path(f"/tmp/{common_name}")
    __openssl_create_csr__(common_name, opensslcnf, private_key_file, csr_file)
    # openssl ca -keyfile /root/tls/private/ec-cakey.pem -cert /root/tls/certs/ec-cacert.pem \
    #   -in server.csr -out server.crt -config /root/tls/openssl.cnf
    cmd = ["openssl", "ca",
           "-keyfile", str(ca_key_file),
           "-cert", str(ca_cert_file),
           "-subj", f"/C=US/CN={common_name}",
           "-in", str(csr_file),
           "-out", str(cert_file),
           "-config", str(opensslcnf),
           # For no prompt use -batch
           "-batch"]
    # if as_server:
    #     "-server"
    # print(" ".join(cmd))
    ret_value = execute_command(cmd)
    csr_file.unlink()
    return ret_value


def __openssl_fingerprint__(cert_file: Path, algorithm: str = "sha1"):

    if algorithm == "sha1":
        algorithm = "-sha1"
    else:
        raise NotImplementedError()

    cmd = ["openssl",
           "x509",
           "-in", str(cert_file),
           "-noout",
           "-fingerprint",
           algorithm]
    ret_value = execute_command(cmd)
    return ret_value
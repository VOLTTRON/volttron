# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}
import copy
import datetime
import logging
from socket import gethostname

import os
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID, ExtensionOID
from cryptography.x509.name import RelativeDistinguishedName
from volttron.platform import get_home
from volttron.platform.agent.utils import load_platform_config

_log = logging.getLogger(__name__)

ROOT_CA_NAME = 'volttron-ca'
DEFAULT_ROOT_CA_CN = '{} {}'.format(gethostname(), ROOT_CA_NAME)
KEY_SIZE = 1024
ENC_STANDARD = 65537
SHA_HASH = 'sha256'
# # days before the certificate will timeout.
DEFAULT_DAYS = 365
# 10 years
DEFAULT_TIMOUT = 60 * 60 * 24 * 360 * 10

PROMPT_PASSPHRASE = False

DEFAULT_CERTS_DIR = os.path.join(get_home(), 'certificates')


class CertError(Exception):
    pass


def _create_subject(**kwargs):
    """
    Create a subject to be used to create a certificate
    :param kwargs: dictionary object containing various details about who we
     are. For a self-signed certificate the subject and issuer are always the
     same.
     Possible arguments:
        C  - Country
        ST - State
        L  - Location
        O  - Organization
        OU - Organizational Unit
        CN - Common Name
    :return: Subject
    :rtype: :class:`x509.Name`
    """

    nameoid_map = {'C': NameOID.COUNTRY_NAME,
                   'ST': NameOID.STATE_OR_PROVINCE_NAME,
                   'L': NameOID.LOCALITY_NAME,
                   'O': NameOID.ORGANIZATION_NAME,
                   'OU': NameOID.ORGANIZATIONAL_UNIT_NAME,
                   'CN': NameOID.COMMON_NAME}
    attributes = []
    for key in ('C', 'ST', 'L', 'O', 'OU', 'CN'):
        if key in kwargs:
            attributes.append(x509.NameAttribute(nameoid_map[key],
                                                 kwargs[key].decode(
                                                     'utf-8')))

    subject = x509.Name(attributes)
    return subject


def _create_fingerprint(public_key):
    pub_bytes = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    h = hashes.Hash(hashes.SHA256(), default_backend())
    h.update(pub_bytes)
    return h.finalize()


def _mk_cacert(**kwargs):
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    issuer = subject = _create_subject(**kwargs)
    cert_builder = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Our certificate will be valid for 365 days
        datetime.datetime.utcnow() + datetime.timedelta(days=DEFAULT_DAYS)
    ).add_extension(
        # set CA to true
        x509.BasicConstraints(ca=True, path_length=1),
        critical=True
    ).serial_number(1).add_extension(
        x509.SubjectKeyIdentifier(
            _create_fingerprint(key.public_key())),
        critical=False
    )
    cert_builder = cert_builder.add_extension(
        x509.KeyUsage(digital_signature=False, key_encipherment=False,
                      content_commitment=False,
                      data_encipherment=False, key_agreement=False,
                      key_cert_sign=True,
                      crl_sign=True,
                      encipher_only=False, decipher_only=False
                      ),
        critical=True)
    # NOTE: M2Crypto code sets SubjectKeyIdentifier extension on
    # with cert.fingerprint() as the value. However can't do the exact same
    # thing in cryptography package as cert object is created only after I
    # call cert_builder.sign but SubjectKeyIdentifier,cert.fingerprint() can
    # be set only to certbuilder. Based on
    # https://security.stackexchange.com/questions/27797/what-damage-could-be-done-if-a-malicious-certificate-had-an-identical-subject-k
    # SubjectKeyIndentifier doesn't seem to be used in cert validation but
    # only in path generation. Though there are other documentation which
    # says it could cause problem in certificate chains. Based on reading docs
    # on the net (https://www.ietf.org/rfc/rfc3280.txt) I have created hash
    # based on public key and used that as SKI.

    cert = cert_builder.sign(
        key, hashes.SHA256(), default_backend())

    print ("Created CA cert")
    return cert, key


def _load_cert(cert_loc):
    with open(cert_loc, 'rb') as cert_file:
        content = cert_file.read()
        cert = x509.load_pem_x509_certificate(content, default_backend())
    return cert


def get_passphrase(verify=True, prompt1='Enter passphrase:',
                   prompt2='Verify passphrase:'):
    """
    Prompt passphrase from user and return it
    :param verify: If user should be prompt twice for verification
    :param prompt1: Prompt to be used for initial input
    :param prompt2: Prompt to used for verification
    :return: The passphrase entered by user
    :type verify: bool
    :type prompt1: str
    :type prompt2: str
    """
    from getpass import getpass
    while 1:
        try:
            p1 = getpass(prompt1)
            if verify:
                p2 = getpass(prompt2)
                if p1 == p2:
                    break
            else:
                break
        except KeyboardInterrupt:
            return None
    return p1


def _load_key(key_file_path):
    passphrase = None
    name = os.path.basename(key_file_path)
    if PROMPT_PASSPHRASE:
        passphrase = get_passphrase(
            prompt1="Enter passphrase for " + name,
            prompt2="Verify passphrase for " + name
        )

    with open(key_file_path, 'rb') as f:
        key = default_backend().load_pem_private_key(
            f.read(),
            passphrase)
        return key


class Certs(object):
    """A wrapper class around certificate creation, retrieval and verification.

    """

    def _cert_file(self, name):
        """
        Returns path to the certificate with passed name. .crt extension is
        added to the passed name be
        :param name: Name of the certificate file
        :return: Full path the <name>.crt file
        :rtype: str
        """
        """"""
        return '/'.join((self.cert_dir, name + '.crt'))

    def _private_key_file(self, name):
        """
        return path to the private key of the passed name. Name passed should
        not contain any file extension as .pem is prefixed
        :param name: name of the key file
        :return: Full path the <name>.pem file
        :rtype: str
        """
        return '/'.join((self.private_dir, name + '.pem'))

    def __init__(self, certificate_dir=DEFAULT_CERTS_DIR):
        """Creates a Certs instance"""
        self.cert_dir = os.path.join(os.path.expanduser(certificate_dir),
                                     'certs')
        self.private_dir = os.path.join(os.path.expanduser(certificate_dir),
                                        'private')

        _log.debug("certs.cert_dir: {}".format(self.cert_dir))
        _log.debug("certs.private_dir: {}".format(self.private_dir))

        # If user provided explicit directory then it should exist
        if not os.path.exists(self.cert_dir):
            if certificate_dir == DEFAULT_CERTS_DIR:
                os.makedirs(self.cert_dir, 0o755)
            else:
                raise ValueError('Invalid cert_dir {}'.format(self.cert_dir))
        if not os.path.exists(self.private_dir):
            if certificate_dir == DEFAULT_CERTS_DIR:
                os.makedirs(self.private_dir, 0o755)
            else:
                raise ValueError('Invalid private_dir {}'.format(self.private_dir))

    def ca_cert(self):
        """
        Get the X509 CA certificate.
        :return: the CA certificate of current volttron instance
        """
        if not self.ca_exists():
            raise CertError("ca certificate doesn't exist")

        return self.cert(ROOT_CA_NAME)

    def cert(self, name):
        """
        Get the X509 certificate based upon the name
        :param name: name of the certificate to be loaded
        :return: The certificate object by the given name
        :rtype: :class: `x509._Certificate`
        """
        if not os.path.exists(self._cert_file(name)):
            raise CertError("invalid certificate path {}".format(
                self._cert_file(name)))
        return _load_cert(self._cert_file(name))

    def cert_exists(self, cert_name):
        """
        Verifies that the cert exists by filename.
        :param cert_name: name of the cert to look up
        :return: True if cert exists, False otherwise
        """
        return os.path.exists(self._cert_file(cert_name))

    def ca_exists(self):
        """
        Returns true if the ca cert has been created already
        :return: True if CA cert exists, False otherwise
        """
        return os.path.exists(self._cert_file(ROOT_CA_NAME))

    def create_ca_signed_cert(self, name, type='client',
                              ca_name=None, **kwargs):
        """
        Create a new certificate and sign it with the volttron instance's
        CA certificate. Save the created certificate and the private key of
        the certificate with the given name
        :param name: name used to save the newly created certificate and
         private key. Files are saved as <name>.crt and <name>.pem
        :param kwargs: dictionary object containing various details about who we
         are.
         Possible arguments:
             C  - Country
             ST - State
             L  - Location
             O  - Organization
             OU - Organizational Unit
             CN - Common Name
        :return: True if certificate creation was successful
        """
        if not ca_name:
            if type == 'CA':
                ca_name = ROOT_CA_NAME
            else:
                platform_config = load_platform_config()
                instance_name = platform_config['instance-name'].strip('"')
                ca_name = instance_name + "-ca"

        ca_cert = self.cert(ca_name)

        issuer = ca_cert.subject
        ski = ca_cert.extensions.get_extension_for_class(
            x509.SubjectKeyIdentifier)

        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        if kwargs:
            subject = _create_subject(**kwargs)
        else:
            temp_list = ca_cert.subject.rdns
            new_attrs = []
            for i in temp_list:
                if i.get_attributes_for_oid(NameOID.COMMON_NAME):
                    new_attrs.append(RelativeDistinguishedName(
                        [x509.NameAttribute(NameOID.COMMON_NAME,
                                            name.decode('utf-8'))]))
                else:
                    new_attrs.append(i)
            subject = x509.Name(new_attrs)

        cert_builder = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            # Our certificate will be valid for 365 days
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).serial_number(2).add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ski),
            critical=False
        )
        if type == 'CA':
            # create a intermediate CA
            cert_builder = cert_builder.add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True
            ).add_extension(
                x509.SubjectKeyIdentifier(
                    _create_fingerprint(key.public_key())),
                critical=False
            )
        else:
            # if type is server or client.
            cert_builder = cert_builder.add_extension(
                x509.KeyUsage(digital_signature=True, key_encipherment=True,
                              content_commitment=False,
                              data_encipherment=False, key_agreement=False,
                              key_cert_sign=False,
                              crl_sign=False,
                              encipher_only=False, decipher_only=False
                              ),
                critical=True)

        if type == 'server':
            # if server cert specify that the certificate can be used as an SSL
            # server certificate
            cert_builder = cert_builder.add_extension(
                x509.ExtendedKeyUsage((ExtendedKeyUsageOID.SERVER_AUTH,)),
                critical=False
            )
        elif type == 'client':
            # specify that the certificate can be used as an SSL
            # client certificate to enable TLS Web Client Authentication
            cert_builder = cert_builder.add_extension(
                x509.ExtendedKeyUsage((ExtendedKeyUsageOID.CLIENT_AUTH,)),
                critical=False
            )

        # 1. version is hardcoded to 2 in Cert builder object. same as what is
        # set by old certs.py

        # 2. No way to set comment. Using M2Crypto it was set using
        # cert.add_ext(X509.new_extension('nsComment', 'SSL sever'))

        ca_key = _load_key(self._private_key_file(ca_name))
        cert = cert_builder.sign(ca_key, hashes.SHA256(), default_backend())
        self._save_cert(name, cert, key)
        return True

    def _save_cert(self, name, cert, pk):
        """
        Save the given certificate and private key using name.crt and
        name.pem respectively.
        :param name: File name to be used to save
        :param cert: :class: `x509._Certificate` object
        :param pk:  :class: `
        :return:
        """
        with open(self._cert_file(name), "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        os.chmod(self._cert_file(name), 0o644)
        encryption = serialization.NoEncryption()
        if PROMPT_PASSPHRASE:
            encryption = serialization.BestAvailableEncryption(
                get_passphrase(prompt1='Enter passphrase for private '
                                       'key ' +
                                       name + ":")
            )

        # Write our key to disk for safe keeping
        with open(self._private_key_file(name), "wb") as f:
            f.write(pk.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=encryption
            ))
        os.chmod(self._private_key_file(name), 0o600)

    def verify_cert(self, cert_name):
        """
        Verify a the given cert is signed by the root ca.
        :param cert_name: The name of the certificate to be verified against
        the CA
        :return:
        """
        cacert = self.ca_cert()
        cert = self.cert(cert_name)
        return cert.verify(cacert.get_pubkey())

    def create_root_ca(self, **kwargs):
        """
        Create a CA certificate with the given args and save it with the given
        name
        :param name: name of the CA certificate
        :param kwargs: Details about the certificate.
         Possible arguments:
            C  - Country
            ST - State
            L  - Location
            O  - Organization
            OU - Organizational Unit
            CN - Common Name
        :return:
        """
        if 'CN' not in kwargs.keys() or kwargs['CN'] is None:
            kwargs['CN'] = DEFAULT_ROOT_CA_CN

        cert, pk = _mk_cacert(**kwargs)
        self._save_cert(ROOT_CA_NAME, cert, pk)
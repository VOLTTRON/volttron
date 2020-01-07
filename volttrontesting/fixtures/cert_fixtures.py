import contextlib
from cryptography.hazmat.primitives import serialization
import os
from types import SimpleNamespace

from volttron.platform.certs import CertWrapper
from volttron.platform.certs import Certs


@contextlib.contextmanager
def certs_profile_1(certificate_dir, fqdn=None, num_server_certs=1, num_client_certs=3):
    """
    Profile 1 generates the specified number of server and client certificates
    all signed by the same self-signed certificate.

    Usage:

        with certs_profile_1("/tmp/abc", 1, 2) as certs:
            ...

    :param certificate_dir:
    :return:
    """

    certs = Certs(certificate_dir)
    data = {'C': 'US',
            'ST': 'Washington',
            'L': 'Richland',
            'O': 'pnnl',
            'OU': 'volttron_test',
            'CN': "myca"}
    ca_cert, ca_pk = certs.create_root_ca(**data)

    ns = SimpleNamespace(ca_cert=ca_cert, ca_key=ca_pk, ca_cert_file=certs.cert_file(certs.root_ca_name),
                         ca_key_file=certs.private_key_file(certs.root_ca_name), server_certs=[], client_certs=[])

    for x in range(num_server_certs):
        cert, key = certs.create_signed_cert_files(f"server{x}", cert_type="server", fqdn=fqdn)

        cert_ns = SimpleNamespace(key=key, cert=cert, cert_file=certs.cert_file(f"server{x}"),
                                  key_file=certs.private_key_file(f"server{x}"))

        ns.server_certs.append(cert_ns)

    for x in range(num_client_certs):

        cert, pk1 = certs.create_signed_cert_files(f"client{x}")
        cert_ns = SimpleNamespace(key=pk1, cert=cert, cert_file=certs.cert_file(f"client{x}"),
                                  key_file=certs.private_key_file(f"client{x}"))
        ns.client_certs.append(cert_ns)

    yield ns

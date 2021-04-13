import contextlib
from cryptography.hazmat.primitives import serialization
import os
from types import SimpleNamespace

from volttron.platform.certs import CertWrapper
from volttron.platform.certs import Certs, _load_key

#TODO: Combine cert_profile_1 and cert_profile_2
# Verify whether we need it as dictionary or SimpleNamespace


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


def certs_profile_2(certificate_dir, fqdn=None, num_server_certs=1, num_client_certs=3):
    """
    Profile 2 generates the specified number of server and client certificates
    all signed by the same self-signed certificate.

    Usage:

        certs = certs_profile_1("/tmp/abc", 1, 2)
            ...

    :param certificate_dir:
    :return: ns
    """

    certs = Certs(certificate_dir)
    data = {'C': 'US',
            'ST': 'Washington',
            'L': 'Richland',
            'O': 'pnnl',
            'OU': 'volttron_test',
            'CN': "myca"}
    if not certs.ca_exists():
        ca_cert, ca_pk = certs.create_root_ca(**data)
    # If the root ca already exists, get ca_cert and ca_pk from current root ca
    else:
        ca_cert = certs.cert(certs.root_ca_name)
        ca_pk = _load_key(certs.private_key_file(certs.root_ca_name))
    # print(f"ca_cert: {ca_cert}")
    # print(f"ca_pk: {ca_pk}")
    # print(f"ca_pk_bytes: {certs.get_pk_bytes(certs.root_ca_name)}")
    ns = dict(ca_cert=ca_cert, ca_key=ca_pk, ca_cert_file=certs.cert_file(certs.root_ca_name),
                         ca_key_file=certs.private_key_file(certs.root_ca_name), server_certs=[], client_certs=[])

    for x in range(num_server_certs):
        cert, key = certs.create_signed_cert_files(f"server{x}", cert_type="server", fqdn=fqdn)

        cert_ns = dict(key=key, cert=cert, cert_file=certs.cert_file(f"server{x}"),
                                  key_file=certs.private_key_file(f"server{x}"))

        ns['server_certs'].append(cert_ns)

    for x in range(num_client_certs):

        cert, pk1 = certs.create_signed_cert_files(f"client{x}")
        cert_ns = dict(key=pk1, cert=cert, cert_file=certs.cert_file(f"client{x}"),
                                  key_file=certs.private_key_file(f"client{x}"))
        ns['client_certs'].append(cert_ns)

    return ns

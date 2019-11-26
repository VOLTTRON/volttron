import contextlib
from cryptography.hazmat.primitives import serialization
import os
from types import SimpleNamespace

from volttron.platform.certs import Certs, GenericCerts


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
    private_dir = os.path.join(certificate_dir, "private")
    public_dir = os.path.join(certificate_dir, "public")
    os.makedirs(private_dir, exist_ok=True)
    os.makedirs(public_dir, exist_ok=True)

    ca_cert, pk = GenericCerts.make_self_signed_ca("myca")
    ca_cert_file = os.path.join(public_dir, "myca.crt")
    with open(ca_cert_file, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    ca_key_file = os.path.join(private_dir, "myca.pem")
    encryption = serialization.NoEncryption()
    with open(ca_key_file, "wb") as f:
        f.write(pk.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption
        ))

    ns = SimpleNamespace(ca_cert=ca_cert, ca_key=pk, ca_cert_file=ca_cert_file, ca_key_file=ca_key_file,
                         server_certs=[], client_certs=[])

    for x in range(num_server_certs):
        cert_file = os.path.join(public_dir, f"server{x}")
        key_file = os.path.join(private_dir, f"server{x}")
        cert, pk1 = GenericCerts.make_signed_cert(ca_cert, pk, f"server{x}", fqdn=fqdn, type="server")
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        encryption = serialization.NoEncryption()
        with open(key_file, "wb") as f:
            f.write(pk1.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=encryption
            ))
        cert_ns = SimpleNamespace(key=pk1, cert=cert, cert_file=cert_file, key_file=key_file)

        ns.server_certs.append(cert_ns)

    for x in range(num_client_certs):
        cert_file = os.path.join(public_dir, f"client{x}")
        key_file = os.path.join(private_dir, f"client{x}")
        cert, pk1 = GenericCerts.make_signed_cert(ca_cert, pk, f"client{x}")
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        encryption = serialization.NoEncryption()
        with open(key_file, "wb") as f:
            f.write(pk1.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=encryption
            ))
        cert_ns = SimpleNamespace(key=pk1, cert=cert, cert_file=cert_file, key_file=key_file)
        ns.client_certs.append(cert_ns)

    yield ns

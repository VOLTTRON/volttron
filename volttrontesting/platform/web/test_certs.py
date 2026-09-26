import json
import os
import pytest
import re
import shutil
from pathlib import Path
from volttron.platform.auth.certs import Certs, Subject, CertError
from volttron.platform.agent.utils import get_platform_instance_name, execute_command
from volttrontesting.utils.platformwrapper import create_volttron_home
from volttrontesting.utils import certs_utils

# certs_utils shells out to the openssl executable (see certs_utils.py), so
# the guard checks for that executable, not a Python module.
HAS_OPENSSL = shutil.which("openssl") is not None


def _extract_cn(subject_text):
    # openssl's subject rendering varies by version ("CN=x" vs "CN = x");
    # match either rather than asserting on the exact text.
    match = re.search(r"CN\s*=\s*([^,\n]+)", subject_text)
    return match.group(1).strip() if match else None


def test_extract_cn_tolerates_openssl_spacing():
    assert _extract_cn("Subject: C = US, CN = RemoteInstanceName.FullyQualifiedIdentity") \
        == "RemoteInstanceName.FullyQualifiedIdentity"
    assert _extract_cn("Subject: C=US, CN=RemoteInstanceName.FullyQualifiedIdentity") \
        == "RemoteInstanceName.FullyQualifiedIdentity"
    assert _extract_cn("Subject: CN=SomeoneElse") != "RemoteInstanceName.FullyQualifiedIdentity"

INSTANCE_NAME = "VC"
PLATFORM_CONFIG = """
#host parameter is mandatory parameter. fully qualified domain name
host: mymachine.pnl.gov

# mandatory. certificate data used to create root ca certificate. Each volttron
# instance must have unique common-name for root ca certificate
certificate-data:
  country: 'US'
  state: 'Washington'
  location: 'Richland'
  organization: 'PNNL'
  organization-unit: 'VOLTTRON Team'
  # volttron_instance has to be replaced with actual instance name of the VOLTTRON
  common-name: 'volttron_instance_root_ca'
# certificate data could also point to existing public and private key files
# of a CA. In that case, use the below certificate-data parameters instead of
# the above. Note. public and private should be pem encoded and use rsa
#  encryption
#
#certificate-data:
#  ca-public-key: /path/to/ca/public/key/ca_pub.crt
#  ca-private-key: /path/to/ca/private/key/ca_private.pem


#
# optional parameters for single instance setup
#
virtual-host: 'volttron' #defaults to volttron

# use the below four port variables if using custom rabbitmq ports
# defaults to 5672
amqp-port: '5672'

# defaults to 5671
amqp-port-ssl: '5671'

# defaults to 15672
mgmt-port: '15672'

# defaults to 15671
mgmt-port-ssl: '15671'

# defaults to true
ssl: 'true'

# defaults to ~/rabbitmq_server/rabbbitmq_server-3.9.29
rmq-home: "~/rabbitmq_server/rabbitmq_server-3.9.29"
"""


@pytest.fixture(scope="function")
def temp_volttron_home(request):
    """
    Create a VOLTTRON_HOME and includes it in the test environment.
    Creates a volttron home, config, and platform_config.yml file
    for testing purposes.
    """
    dirpath = create_volttron_home()
    os.environ['VOLTTRON_HOME'] = dirpath
    debug_flag = os.environ.get('DEBUG', True)
    with open(os.path.join(dirpath, "platform_config.yml"), 'w') as fp:
        fp.write(PLATFORM_CONFIG)

    with open(os.path.join(dirpath, "config"), "w") as fp:
        fp.write("[volttron]\n")
        fp.write("instance-name = {}\n".format(INSTANCE_NAME))
    yield dirpath

    if not debug_flag:
        shutil.rmtree(dirpath, ignore_errors=True)
        assert not os.path.exists(dirpath)


@pytest.fixture(scope="function")
def temp_csr(request):
    """
    Create a Certificate Signing Request (CSR) using the Certs class.
    Use this CSR to test approving, denying, and deleting CSRs
    """
    certs = Certs()
    data = {'C': 'US',
            'ST': 'Washington',
            'L': 'Richland',
            'O': 'pnnl',
            'OU': 'volttron',
            'CN': INSTANCE_NAME+"_root_ca"}
    certs.create_root_ca(**data)
    assert certs.ca_exists()

    certs.create_signed_cert_files(name="FullyQualifiedIdentity", ca_name=certs.root_ca_name)

    csr = certs.create_csr("FullyQualifiedIdentity", "RemoteInstanceName")
    yield certs, csr

    shutil.rmtree(certs.default_certs_dir, ignore_errors=True)
    assert not os.path.exists(certs.default_certs_dir)


def test_certificate_directories(temp_volttron_home):
    certs = Certs()
    paths = (certs.certs_pending_dir, certs.private_dir, certs.cert_dir,
             certs.remote_cert_dir, certs.csr_pending_dir, certs.ca_db_dir)

    for p in paths:
        assert os.path.exists(p)


@pytest.mark.skipif(not HAS_OPENSSL, reason="Requires the openssl executable on PATH")
def test_create_root_ca(temp_volttron_home):
    certs = Certs()
    assert not certs.ca_exists()
    data = {'C': 'US',
            'ST': 'Washington',
            'L': 'Richland',
            'O': 'pnnl',
            'OU': 'volttron',
            'CN': INSTANCE_NAME+"_root_ca"}
    certs.create_root_ca(**data)
    assert certs.ca_exists()

    private_key = certs.private_key_file("VC-root-ca")
    cert_file = certs.cert_file("VC-root-ca")
    # The cnf file lives beside this test, not in the CWD.
    tls = certs_utils.TLSRepository(repo_dir=temp_volttron_home,
                                     openssl_cnffile=str(Path(__file__).parent / "openssl.cnf"),
                                     serverhost="FullyQualifiedIdentity")
    assert tls.verify_ca_cert(private_key, cert_file)


@pytest.mark.skipif(not HAS_OPENSSL, reason="Requires the openssl executable on PATH")
def test_verify_ca_cert_rejects_mismatched_key(temp_volttron_home):
    # verify_ca_cert must reject a cert paired with an unrelated key, not
    # just accept a matching one.
    certs = Certs()
    data = {'C': 'US',
            'ST': 'Washington',
            'L': 'Richland',
            'O': 'pnnl',
            'OU': 'volttron',
            'CN': INSTANCE_NAME+"_root_ca"}
    certs.create_root_ca(**data)
    cert_file = certs.cert_file("VC-root-ca")

    other_key_file = os.path.join(temp_volttron_home, "unrelated.pem")
    execute_command(["openssl", "genrsa", "-out", other_key_file, "2048"])

    tls = certs_utils.TLSRepository(repo_dir=temp_volttron_home,
                                     openssl_cnffile=str(Path(__file__).parent / "openssl.cnf"),
                                     serverhost="FullyQualifiedIdentity")
    assert tls.verify_ca_cert(other_key_file, cert_file) is False


@pytest.mark.skipif(not HAS_OPENSSL, reason="Requires the openssl executable on PATH")
def test_verify_ca_cert_accepts_matching_ec_pair(temp_volttron_home):
    # verify_ca_cert must accept a genuinely matching EC pair too: this
    # module's own CA key is EC P-256 (see __openssl_create_private_key__),
    # and a modulus-only check (RSA-specific) reports False for it even
    # though it matches.
    tls = certs_utils.TLSRepository(repo_dir=temp_volttron_home,
                                     openssl_cnffile=str(Path(__file__).parent / "openssl.cnf"),
                                     serverhost="FullyQualifiedIdentity")
    assert tls.verify_ca_cert(tls.ca_key_file, tls.ca_cert_file) is True


def test_create_signed_cert_files(temp_volttron_home):
    certs = Certs()
    assert not certs.cert_exists("test_cert")

    data = {'C': 'US',
            'ST': 'Washington',
            'L': 'Richland',
            'O': 'pnnl',
            'OU': 'volttron',
            'CN': INSTANCE_NAME+"_root_ca"}
    certs.create_root_ca(**data)
    assert certs.ca_exists()

    certs.create_signed_cert_files("test_cert")
    assert certs.cert_exists("test_cert")

    existing_cert = certs.create_signed_cert_files("test_cert")
    assert existing_cert[0] == certs.cert("test_cert")


@pytest.mark.skipif(not HAS_OPENSSL, reason="Requires the openssl executable on PATH")
def test_create_csr(temp_volttron_home):
    # Use TLS repo to create a CA
    # The cnf file lives beside this test, not in the CWD.
    tls = certs_utils.TLSRepository(repo_dir=temp_volttron_home,
                                     openssl_cnffile=str(Path(__file__).parent / "openssl.cnf"),
                                     serverhost="FullyQualifiedIdentity")
    tls.__create_ca__()
    certs_using_tls = Certs(temp_volttron_home)

    assert certs_using_tls.cert_exists("VC-root-ca")
    assert Path(certs_using_tls.cert_file("VC-root-ca")) == tls._ca_cert
   
    # Create Volttron CSR using TLS repo CA
    csr = certs_using_tls.create_csr("FullyQualifiedIdentity", "RemoteInstanceName")

    # Write CSR to a file to verify
    csr_file_path = os.path.join(certs_using_tls.cert_dir, "CSR.csr")
    csr_private_key_path = certs_using_tls.private_key_file("FullyQualifiedIdentity")
    with open(csr_file_path, "wb") as f:
        f.write(csr)

    # verify_csr returns False on failure (not a raise), so "!= None" can
    # never fail here; assert on the result and the subject instead of on
    # openssl's message wording, which is not stable across versions.
    csr_info = tls.verify_csr(csr_file_path, csr_private_key_path)
    assert csr_info is not False
    assert _extract_cn(csr_info) == "RemoteInstanceName.FullyQualifiedIdentity"


@pytest.mark.skipif(not HAS_OPENSSL, reason="Requires the openssl executable on PATH")
def test_verify_csr_returns_false_for_wrong_key(temp_volttron_home):
    # A CSR verified against the wrong key must report False, not raise
    # (a bad verify is a test FAILURE, not an ERROR). The wrong key must be
    # the same type (EC P-256, like every key this module generates) or
    # openssl fails on key type, not on mismatch, which proves nothing
    # about the mismatch check.
    tls = certs_utils.TLSRepository(repo_dir=temp_volttron_home,
                                     openssl_cnffile=str(Path(__file__).parent / "openssl.cnf"),
                                     serverhost="FullyQualifiedIdentity")
    tls.__create_ca__()
    certs_using_tls = Certs(temp_volttron_home)
    csr = certs_using_tls.create_csr("FullyQualifiedIdentity", "RemoteInstanceName")

    csr_file_path = os.path.join(certs_using_tls.cert_dir, "CSR2.csr")
    with open(csr_file_path, "wb") as f:
        f.write(csr)

    wrong_key_path = os.path.join(temp_volttron_home, "wrong.pem")
    execute_command(["openssl", "ecparam", "-out", wrong_key_path, "-name", "prime256v1", "-genkey"])

    assert tls.verify_csr(csr_file_path, wrong_key_path) is False


@pytest.mark.skipif(not HAS_OPENSSL, reason="Requires the openssl executable on PATH")
def test_signed_cert_csr_stays_in_cert_directory(monkeypatch, temp_volttron_home):
    # The CSR TLSRepository creates while signing a cert used to land at a
    # fixed /tmp path. The property is containment in the certificate
    # directory, not "not under /tmp": a platform's own VOLTTRON_HOME (and
    # this fixture's temp_volttron_home) can itself be under /tmp, which is
    # a legitimate location, not a regression.
    tls = certs_utils.TLSRepository(repo_dir=temp_volttron_home,
                                     openssl_cnffile=str(Path(__file__).parent / "openssl.cnf"),
                                     serverhost="FullyQualifiedIdentity")

    seen = {}

    def spy_create_csr(common_name, opensslcnf, private_key_file, server_csr_file):
        seen["csr_path"] = Path(server_csr_file).resolve()
        return ""

    monkeypatch.setattr(certs_utils, "__openssl_create_csr__", spy_create_csr)

    cert_dir = tls.__get_cert_file__("AnotherIdentity").resolve().parent
    try:
        tls.create_cert("AnotherIdentity", as_server=False)
    except Exception:
        # The signing step fails downstream of the CSR write (the stub
        # wrote nothing real); only the computed CSR path is under test.
        pass

    assert "csr_path" in seen
    assert seen["csr_path"].parent == cert_dir


@pytest.mark.skipif(not HAS_OPENSSL, reason="Requires the openssl executable on PATH")
def test_signed_cert_rejects_traversal_common_name(monkeypatch, temp_volttron_home):
    # A common_name of "../escape" must not walk the transient CSR out of
    # the certificate directory: the containment guard must refuse it
    # outright, and the CSR write must never be attempted.
    tls = certs_utils.TLSRepository(repo_dir=temp_volttron_home,
                                     openssl_cnffile=str(Path(__file__).parent / "openssl.cnf"),
                                     serverhost="FullyQualifiedIdentity")

    calls = []
    monkeypatch.setattr(certs_utils, "__openssl_create_csr__",
                         lambda *args, **kwargs: calls.append(args))

    with pytest.raises(ValueError):
        tls.create_cert("../escape", as_server=False)

    assert calls == []


def test_approve_csr(temp_volttron_home, temp_csr):
    certs = temp_csr[0]
    csr = temp_csr[1]

    # Save pending CSR request into a CSR file
    csr_file = certs.save_pending_csr_request("10.1.1.1", "test_csr", csr)
    f = open(csr_file, "rb")
    assert f.read() == csr
    f.close()

    # Check meta data saved in file for CSR
    csr_meta_file = os.path.join(certs.csr_pending_dir, "test_csr.json")
    f = open(csr_meta_file, "r")
    data = f.read()
    csr_meta_data = json.loads(data)
    f.close()
    assert csr_meta_data['status'] == "PENDING"
    assert csr_meta_data['csr'] == csr.decode("utf-8")

    # Approve the CSR
    signed_cert = certs.approve_csr("test_csr")
    f = open(csr_meta_file, "r")
    updated_data = f.read()
    approved_csr_meta_data = json.loads(updated_data)
    f.close()
    assert approved_csr_meta_data['status'] == "APPROVED"


def test_deny_csr(temp_volttron_home, temp_csr):
    certs = temp_csr[0]
    csr = temp_csr[1]

    # Save pending CSR request into a CSR file
    csr_file = certs.save_pending_csr_request("10.1.1.1", "test_csr", csr)
    f = open(csr_file, "rb")
    assert f.read() == csr
    f.close()

    # Check meta data saved in file for CSR
    csr_meta_file = os.path.join(certs.csr_pending_dir, "test_csr.json")
    f = open(csr_meta_file, "r")
    data = f.read()
    csr_meta_data = json.loads(data)
    f.close()
    assert csr_meta_data['status'] == "PENDING"
    assert csr_meta_data['csr'] == csr.decode("utf-8")

    # Deny the CSR
    certs.deny_csr("test_csr")
    f = open(csr_meta_file, "r")
    updated_data = f.read()
    denied_csr_meta_data = json.loads(updated_data)
    f.close()
    
    # Check that the CSR was denied, the pending CSR files still exist, and the cert has been removed
    assert denied_csr_meta_data['status'] == "DENIED"
    assert os.path.exists(csr_meta_file)
    assert os.path.exists(csr_file)
    assert certs.cert_exists("test_csr") == False


def test_delete_csr(temp_volttron_home, temp_csr):
    certs = temp_csr[0]
    csr = temp_csr[1]

    # Save pending CSR request into a CSR file
    csr_file = certs.save_pending_csr_request("10.1.1.1", "test_csr", csr)
    f = open(csr_file, "rb")
    assert f.read() == csr
    f.close()

    # Check meta data saved in file for CSR
    csr_meta_file = os.path.join(certs.csr_pending_dir, "test_csr.json")
    f = open(csr_meta_file, "r")
    data = f.read()
    csr_meta_data = json.loads(data)
    f.close()
    assert csr_meta_data['status'] == "PENDING"
    assert csr_meta_data['csr'] == csr.decode("utf-8")

    # Delete CSR
    certs.delete_csr("test_csr")

    # Check that the CSR files have been deleted and the cert has been removed
    assert os.path.exists(csr_meta_file) == False
    assert os.path.exists(csr_file) == False
    assert certs.cert_exists("test_csr") == False

    



# def test_cadb_updated(temp_volttron_home):
#     certs = Certs()
#     certs.create_root_ca()
#     instance_name = get_platform_instance_name(False)
#     assert not os.path.exists(certs.ca_db_file(instance_name))
#     certs.create_instance_ca(instance_name)
#     assert os.path.exists(certs.ca_db_file(instance_name))
#
#
# def test_create_instance_ca(temp_volttron_home):
#     certs = Certs()
#     certs.create_root_ca()
#     instance_name = get_platform_instance_name(False)
#     assert instance_name == INSTANCE_NAME
#     assert not certs.cert_exists(instance_name)
#     certs.create_instance_ca(instance_name)
#     assert certs.cert_exists(instance_name)
#     assert certs.verify_cert(instance_name)

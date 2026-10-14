"""
Tests for the /csr/request_new endpoint and the test harness's CSR approval
helpers.

The platform never signs a CSR on its own: a request is recorded as PENDING
and must be approved by an administrator through the auth service.  The
PlatformWrapper helpers (``approve_pending_csrs``/``start_csr_approver``) and
``vctl auth remote approve`` are two front ends to that same RPC, and both are
exercised here.

These tests only run against an rmq instance with web enabled.
"""
import gevent
import pytest
import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from volttron.platform import jsonapi
from volttron.platform.agent.known_identities import AUTH
from volttron.platform.agent.utils import execute_command
from volttrontesting.skip_if_handlers import skip_zmq


def _make_csr(common_name: str) -> str:
    """Build a PEM CSR whose subject common name is ``common_name``."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    csr = x509.CertificateSigningRequestBuilder().subject_name(
        x509.Name([
            # The CA database records C/ST/L/O/OU/CN, so a signable CSR needs all six
            # (the platform's own Certs.create_csr copies them from the root CA).
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Washington"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Richland"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PNNL"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "VOLTTRON"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
    ).sign(key, hashes.SHA256(), default_backend())
    return csr.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def _request_csr(instance, common_name: str, csr_pem: str) -> dict:
    """POST a CSR exactly the way Core.request_cert does and return the json body."""
    payload = dict(csr=csr_pem, identity=common_name, hostname="localhost")
    response = requests.post(instance.bind_web_address + "/csr/request_new",
                             json=jsonapi.dumps(payload),
                             verify=instance.requests_ca_bundle or True,
                             timeout=10)
    response.raise_for_status()
    return response.json()


@pytest.fixture
def csr_instance(volttron_instance_web):
    # volttron_instance_web comes from volttrontesting/conftest.py.
    skip_zmq(volttron_instance_web)
    yield volttron_instance_web
    volttron_instance_web.stop_csr_approver()


def _unique_cn(instance, tag):
    import uuid
    return f"{instance.instance_name}.webcsr_{tag}_{uuid.uuid4().hex[:8]}"


def test_csr_is_pending_until_explicitly_approved(csr_instance):
    instance = csr_instance
    cn = _unique_cn(instance, "explicit")
    csr_pem = _make_csr(cn)

    first = _request_csr(instance, cn, csr_pem)
    assert first["status"] == "PENDING"
    assert "cert" not in first
    assert cn in instance.pending_csrs()

    # Nothing is signed until an administrator acts.
    again = _request_csr(instance, cn, csr_pem)
    assert again["status"] == "PENDING"

    approved = instance.approve_pending_csrs(expected=[cn], timeout=10)
    assert approved == {cn}
    assert cn not in instance.pending_csrs()

    status = instance.dynamic_agent.vip.rpc(AUTH, "get_authorization_status", cn).get(timeout=5)
    assert status == "APPROVED"

    after = _request_csr(instance, cn, csr_pem)
    assert after["status"] == "APPROVED"
    assert after["cert"].startswith("-----BEGIN CERTIFICATE-----")


def test_csr_approver_greenlet_approves_new_requests(csr_instance):
    instance = csr_instance
    assert not instance.csr_approver_running

    instance.start_csr_approver(poll_interval=0.2)
    assert instance.csr_approver_running
    # idempotent
    instance.start_csr_approver()
    assert instance.csr_approver_running

    cn = _unique_cn(instance, "greenlet")
    csr_pem = _make_csr(cn)
    assert _request_csr(instance, cn, csr_pem)["status"] == "PENDING"

    # A remote retries while pending; emulate that until the approver has acted.
    result = None
    with gevent.Timeout(20, False):
        while True:
            result = _request_csr(instance, cn, csr_pem)
            if result["status"] == "APPROVED":
                break
            gevent.sleep(0.5)
    assert result is not None and result["status"] == "APPROVED", result
    assert result["cert"].startswith("-----BEGIN CERTIFICATE-----")

    instance.stop_csr_approver()
    assert not instance.csr_approver_running

    # With the approver stopped a new request stays pending.
    cn2 = _unique_cn(instance, "stopped")
    csr2 = _make_csr(cn2)
    _request_csr(instance, cn2, csr2)
    gevent.sleep(2)
    assert _request_csr(instance, cn2, csr2)["status"] == "PENDING"
    assert cn2 in instance.pending_csrs()


def test_csr_with_foreign_instance_name_is_rejected(csr_instance):
    instance = csr_instance
    cn = f"not_{instance.instance_name}.webcsr_foreign"
    result = _request_csr(instance, cn, _make_csr(cn))
    assert result["status"] == "ERROR"
    assert instance.instance_name in result["message"]
    assert cn not in instance.pending_csrs()


def test_vctl_auth_remote_approve_cli(csr_instance):
    """The operator path: list the pending CSR and approve it with vctl."""
    instance = csr_instance
    cn = _unique_cn(instance, "vctl")
    csr_pem = _make_csr(cn)
    assert _request_csr(instance, cn, csr_pem)["status"] == "PENDING"

    env = instance.env.copy()
    listing = execute_command(["volttron-ctl", "auth", "remote", "list", "--status", "pending"], env=env)
    assert cn in listing

    execute_command(["volttron-ctl", "auth", "remote", "approve", cn], env=env)

    after = _request_csr(instance, cn, csr_pem)
    assert after["status"] == "APPROVED"
    assert after["cert"].startswith("-----BEGIN CERTIFICATE-----")

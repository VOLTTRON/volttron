"""
In-process tests of CSREndpoints._csr_request_new.

Certs and the platform instance name are patched, so no platform, broker or
web server is started and the tests run in every CI job that collects this
directory.
"""
import contextlib
from unittest import mock

import pytest

from volttron.platform import jsonapi
from volttron.platform.web.csr_endpoints import CSREndpoints

INSTANCE = "volttron1"
# The only Certs methods the handler may call. Anything else, such as a signing
# or approval call, means the endpoint acts on a request without an administrator.
ALLOWED_CERTS_CALLS = {"get_csr_common_name", "save_pending_csr_request",
                       "get_csr_status", "get_cert_from_csr"}
REMOTE_ADDR = "10.1.2.3"
CSR_PEM = "-----BEGIN CERTIFICATE REQUEST-----\nfake\n-----END CERTIFICATE REQUEST-----\n"


@pytest.fixture
def certs():
    with mock.patch("volttron.platform.web.csr_endpoints.Certs") as certs_class:
        yield certs_class.return_value
        called = {c[0] for c in certs_class.return_value.mock_calls}
        assert called <= ALLOWED_CERTS_CALLS, sorted(called - ALLOWED_CERTS_CALLS)


@pytest.fixture
def endpoints(certs):
    with mock.patch("volttron.platform.web.csr_endpoints.get_platform_instance_name",
                    return_value=INSTANCE):
        yield CSREndpoints(mock.MagicMock())


def _post(endpoints, certs, common_name, status, cert=None):
    certs.get_csr_common_name.return_value = common_name
    certs.get_csr_status.return_value = status
    certs.get_cert_from_csr.return_value = cert
    response = endpoints._csr_request_new({"REMOTE_ADDR": REMOTE_ADDR},
                                          jsonapi.dumps(dict(csr=CSR_PEM)))
    return jsonapi.loads(response.get_data(as_text=True))


def test_new_request_is_saved_and_answered_pending(endpoints, certs):
    identity = INSTANCE + ".agent"
    body = _post(endpoints, certs, identity, "PENDING")

    assert body == dict(status="PENDING", message="The request is pending administrator approval.")
    certs.save_pending_csr_request.assert_called_once_with(REMOTE_ADDR, identity,
                                                           CSR_PEM.encode("utf-8"))
    certs.get_cert_from_csr.assert_not_called()
    certs.approve_csr.assert_not_called()


def test_request_is_recorded_before_its_status_is_read(endpoints, certs):
    order = mock.Mock()
    order.attach_mock(certs.save_pending_csr_request, "save")
    order.attach_mock(certs.get_csr_status, "status")
    _post(endpoints, certs, INSTANCE + ".agent", "PENDING")

    assert [c[0] for c in order.mock_calls] == ["save", "status"]


def test_approved_request_gets_the_cert(endpoints, certs):
    body = _post(endpoints, certs, INSTANCE + ".agent", "APPROVED", cert=b"CERT-PEM")

    assert body == dict(status="APPROVED", cert="CERT-PEM")
    certs.get_cert_from_csr.assert_called_once_with(INSTANCE + ".agent")


def test_denied_request_is_answered_denied_without_cert(endpoints, certs):
    body = _post(endpoints, certs, INSTANCE + ".agent", "DENIED")

    assert body == dict(status="DENIED", message="The request has been denied by the administrator.")
    certs.get_cert_from_csr.assert_not_called()


def test_unknown_status_names_the_identity(endpoints, certs):
    identity = INSTANCE + ".agent"
    body = _post(endpoints, certs, identity, "UNKNOWN")

    assert body == dict(status="UNKNOWN",
                        message="An unknown common name was specified to the server " + identity)
    certs.get_cert_from_csr.assert_not_called()


def test_unrecognised_status_gets_the_generic_error(endpoints, certs):
    body = _post(endpoints, certs, INSTANCE + ".agent", "SURPRISE")

    assert body == dict(status="SURPRISE",
                        message="An unknown error has occurred during the response phase")
    certs.get_cert_from_csr.assert_not_called()


@pytest.mark.parametrize("common_name", [
    "other_instance.agent",
    INSTANCE + "evil.agent",
    "other." + INSTANCE + ".agent",
    INSTANCE.upper() + ".agent",
    INSTANCE,
    ".agent",
])
def test_name_outside_this_instance_is_refused_and_not_saved(endpoints, certs, common_name):
    body = _post(endpoints, certs, common_name, "APPROVED", cert=b"CERT-PEM")

    assert body == dict(status="ERROR", message="CSR must start with instance name: " + INSTANCE)
    certs.save_pending_csr_request.assert_not_called()
    certs.get_csr_status.assert_not_called()
    certs.get_cert_from_csr.assert_not_called()


def test_dict_body_is_accepted(endpoints, certs):
    certs.get_csr_common_name.return_value = INSTANCE + ".agent"
    certs.get_csr_status.return_value = "PENDING"
    response = endpoints._csr_request_new({"REMOTE_ADDR": REMOTE_ADDR}, dict(csr=CSR_PEM))

    assert jsonapi.loads(response.get_data(as_text=True))["status"] == "PENDING"
    certs.save_pending_csr_request.assert_called_once()


def test_approved_status_with_no_stored_cert_answers_null_cert(endpoints, certs):
    body = _post(endpoints, certs, INSTANCE + ".agent", "APPROVED", cert=None)

    assert body == dict(status="APPROVED", cert=None)
    certs.get_cert_from_csr.assert_called_once_with(INSTANCE + ".agent")


def test_malformed_json_saves_nothing(endpoints, certs):
    endpoints._csr_request_new({"REMOTE_ADDR": REMOTE_ADDR}, "{not json")

    certs.save_pending_csr_request.assert_not_called()
    certs.get_cert_from_csr.assert_not_called()


@pytest.mark.xfail(strict=True, reason="#3381 malformed JSON gets an empty 200")
def test_malformed_json_gets_an_error_response_with_json_body(endpoints, certs):
    response = endpoints._csr_request_new({"REMOTE_ADDR": REMOTE_ADDR}, "{not json")

    body = jsonapi.loads(response.get_data(as_text=True))
    assert body["status"] == "ERROR"
    assert body["message"]


def test_body_without_csr_saves_nothing(endpoints, certs):
    with contextlib.suppress(Exception):
        endpoints._csr_request_new({"REMOTE_ADDR": REMOTE_ADDR}, jsonapi.dumps(dict(identity="x")))

    certs.save_pending_csr_request.assert_not_called()
    certs.get_cert_from_csr.assert_not_called()


@pytest.mark.xfail(strict=True, reason="#3381 a body without csr raises AttributeError")
def test_body_without_csr_gets_an_error_response_with_json_body(endpoints, certs):
    response = endpoints._csr_request_new({"REMOTE_ADDR": REMOTE_ADDR},
                                          jsonapi.dumps(dict(identity="x")))

    body = jsonapi.loads(response.get_data(as_text=True))
    assert body["status"] == "ERROR"
    assert body["message"]

import base64
import hashlib
import hmac
import json
import logging
import subprocess
import sys
import types

import jwt
import pytest
from mock import MagicMock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import volttron.platform.web as web
from volttron.platform import is_web_available
from volttron.platform.web import PlatformWebService, get_user_claim_from_bearer
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.platform.web.authenticate_endpoint import AuthenticateEndpoints
from volttron.utils import get_random_key
from volttrontesting.fixtures.volttron_platform_fixtures import get_test_volttron_home
from volttrontesting.utils.web_utils import get_test_web_env

USER = "token_user"
PASSWORD = "Pass123"


def _rsa_pem_pair():
    # Same serialization the web service gets from CertWrapper.
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(encoding=serialization.Encoding.PEM,
                                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                                    encryption_algorithm=serialization.NoEncryption())
    public_pem = key.public_key().public_bytes(encoding=serialization.Encoding.PEM,
                                               format=serialization.PublicFormat.SubjectPublicKeyInfo)
    return private_pem, public_pem


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _hand_built_token(alg: str, claims: dict, hmac_key: bytes = None) -> str:
    # Built by hand because PyJWT refuses to sign some of these combinations.
    signing_input = _b64url(json.dumps({"alg": alg, "typ": "JWT"}).encode()) + "." + \
        _b64url(json.dumps(claims).encode())
    signature = b""
    if hmac_key is not None:
        signature = hmac.new(hmac_key, signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + _b64url(signature)


@pytest.fixture(params=["HS256", "RS256"])
def server(request):
    """Yields (endpoints, algorithm, verify_key) with one admin user stored."""
    with get_test_volttron_home(messagebus="zmq"):
        AdminEndpoints().add_user(USER, PASSWORD, groups=["admin"])
        if request.param == "HS256":
            secret = get_random_key()
            endpoints = AuthenticateEndpoints(web_secret_key=secret)
            verify_key = secret
        else:
            private_pem, public_pem = _rsa_pem_pair()
            endpoints = AuthenticateEndpoints(tls_private_key=private_pem, tls_public_key=public_pem)
            verify_key = public_pem
        try:
            yield endpoints, request.param, verify_key
        finally:
            endpoints._observer.stop()


def _login(endpoints):
    env = get_test_web_env("/authenticate", method="POST")
    response = endpoints.handle_authenticate(env, {"username": USER, "password": PASSWORD})
    assert "200 OK" in response.status
    return json.loads(response.response[0].decode("utf-8"))


def _renew(endpoints, refresh_token, data=None, authorization=None):
    env = get_test_web_env("/authenticate", method="PUT")
    env["HTTP_AUTHORIZATION"] = authorization if authorization is not None else "BEARER " + refresh_token
    return endpoints.handle_authenticate(env, data={} if data is None else data)


def _assert_refused(response, label):
    assert response.status.startswith("401"), (label, response.status)
    assert "access_token" not in response.response[0].decode("utf-8"), label


def test_get_tokens_returns_str_tokens_signed_with_server_key(server):
    endpoints, algorithm, verify_key = server

    access_token, refresh_token = endpoints._get_tokens({"groups": ["admin"]})

    assert type(access_token) is str
    assert type(refresh_token) is str
    access = jwt.decode(access_token, verify_key, algorithms=[algorithm])
    refresh = jwt.decode(refresh_token, verify_key, algorithms=[algorithm])
    assert jwt.get_unverified_header(access_token)["alg"] == algorithm
    assert access["grant_type"] == "access_token"
    assert refresh["grant_type"] == "refresh_token"
    assert access["groups"] == refresh["groups"] == ["admin"]
    assert access["exp"] - access["iat"] == endpoints.access_token_timeout * 60
    assert refresh["exp"] - refresh["iat"] == endpoints.refresh_token_timeout * 60


def test_login_and_renew_return_str_tokens(server):
    endpoints, algorithm, verify_key = server

    tokens = _login(endpoints)
    assert jwt.decode(tokens["access_token"], verify_key, algorithms=[algorithm])["grant_type"] == "access_token"

    response = _renew(endpoints, tokens["refresh_token"])

    assert "200 OK" in response.status
    renewed = json.loads(response.response[0].decode("utf-8"))["access_token"]
    assert jwt.get_unverified_header(renewed)["alg"] == algorithm
    claims = jwt.decode(renewed, verify_key, algorithms=[algorithm])
    assert claims["grant_type"] == "access_token"
    assert claims["groups"] == ["admin"]


def _other_algorithm_tokens(algorithm, verify_key):
    claims = {"groups": ["admin"], "grant_type": "refresh_token"}
    tokens = {"none": _hand_built_token("none", claims)}
    if algorithm == "RS256":
        # An HS256 token keyed with the server's own public key.
        tokens["HS256"] = _hand_built_token("HS256", claims, hmac_key=verify_key)
    else:
        other_private, _ = _rsa_pem_pair()
        tokens["RS256"] = jwt.encode(claims, other_private, algorithm="RS256")
    return tokens


def test_renew_refuses_refresh_token_with_other_algorithm(server):
    endpoints, algorithm, verify_key = server

    tokens = _other_algorithm_tokens(algorithm, verify_key)
    assert len(tokens) == 2

    for alg, token in tokens.items():
        _assert_refused(_renew(endpoints, token), alg)


def test_bearer_decode_refuses_other_algorithm(server):
    _, algorithm, verify_key = server
    kwargs = {"web_secret_key": verify_key} if algorithm == "HS256" else {"tls_public_key": verify_key}

    tokens = _other_algorithm_tokens(algorithm, verify_key)
    assert len(tokens) == 2

    for alg, token in tokens.items():
        with pytest.raises(jwt.InvalidAlgorithmError):
            get_user_claim_from_bearer(token, **kwargs)


def test_renew_refuses_wrong_key_and_malformed_refresh_tokens(server):
    endpoints, algorithm, _ = server
    claims = {"groups": ["admin"], "grant_type": "refresh_token"}
    if algorithm == "HS256":
        wrong_key = get_random_key()
    else:
        wrong_key, _ = _rsa_pem_pair()
    tokens = {"wrong key": jwt.encode(claims, wrong_key, algorithm=algorithm),
              "malformed": "not.a.jwt"}

    for label, token in tokens.items():
        _assert_refused(_renew(endpoints, token), label)


@pytest.mark.parametrize("authorization", ["Bearer", "Bearer two tokens", ""])
def test_renew_refuses_malformed_authorization_header(server, authorization):
    endpoints, _, _ = server
    refresh_token = _login(endpoints)["refresh_token"]

    _assert_refused(_renew(endpoints, refresh_token, authorization=authorization), authorization)


@pytest.mark.parametrize("body", ["not json", "[1, 2]", "\"text\""])
def test_renew_refuses_body_that_is_not_a_json_object(server, body):
    endpoints, _, _ = server
    refresh_token = _login(endpoints)["refresh_token"]

    _assert_refused(_renew(endpoints, refresh_token, data=body), body)


@pytest.mark.parametrize("body", ["", '{"current_access_token": "x"}', {}])
def test_renew_accepts_empty_or_json_object_body(server, body):
    endpoints, algorithm, verify_key = server
    refresh_token = _login(endpoints)["refresh_token"]

    response = _renew(endpoints, refresh_token, data=body)

    assert "200 OK" in response.status
    renewed = json.loads(response.response[0].decode("utf-8"))["access_token"]
    assert jwt.decode(renewed, verify_key, algorithms=[algorithm])["grant_type"] == "access_token"


@pytest.mark.parametrize("error", [jwt.InvalidSignatureError("bad"), jwt.DecodeError("bad")])
def test_jsonrpc_authentication_refuses_undecodable_token(error, caplog):
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.get_user_claims = MagicMock(side_effect=error)

    with caplog.at_level(logging.ERROR):
        assert svc.jsonrpc_verify_and_dispatch("token") is False
    assert any("invalid token" in r.getMessage() for r in caplog.records)


def test_bearer_decode_passes_server_algorithm_list(server, monkeypatch):
    endpoints, algorithm, verify_key = server
    kwargs = {"web_secret_key": verify_key} if algorithm == "HS256" else {"tls_public_key": verify_key}
    access_token, _ = endpoints._get_tokens({"groups": ["admin"]})
    seen = []
    real_decode = jwt.decode

    def recording_decode(*args, **kw):
        seen.append(kw.get("algorithms"))
        return real_decode(*args, **kw)

    monkeypatch.setattr(jwt, "decode", recording_decode)

    claims = get_user_claim_from_bearer(access_token, **kwargs)

    assert claims["groups"] == ["admin"]
    assert seen == [[algorithm]]


def test_unused_claim_helpers_are_removed():
    assert not hasattr(web, "get_user_claims")
    assert not hasattr(web, "__get_key_and_algorithm__")
    assert not hasattr(PlatformWebService, "_authenticate_route")


_IMPORT_WEB = """
import sys, types
mode = sys.argv[1]
if mode == "missing":
    sys.modules["jwt"] = None
elif mode != "installed":
    fake = types.ModuleType("jwt")
    if mode != "noversion":
        fake.__version__ = {"old": "1.7.1", "badversion": "two.0"}[mode]
    sys.modules["jwt"] = fake
try:
    import volttron.platform.web
except ImportError as exc:
    print(exc)
    sys.exit(3)
"""


@pytest.mark.parametrize("mode, returncode, message", [
    ("installed", 0, ""),
    ("missing", 3, "requires PyJWT 2"),
    ("old", 3, "requires PyJWT 2, found 1.7.1"),
    ("noversion", 3, "requires PyJWT 2, found an unknown version"),
    ("badversion", 3, "requires PyJWT 2, found an unknown version"),
])
def test_web_import_names_pyjwt_requirement(mode, returncode, message):
    result = subprocess.run([sys.executable, "-c", _IMPORT_WEB, mode],
                            capture_output=True, text=True, timeout=60)

    assert result.returncode == returncode, result.stdout + result.stderr
    assert message in result.stdout


def _fake_jwt(version):
    fake = types.ModuleType("jwt")
    fake.__version__ = version
    return fake


@pytest.mark.parametrize("module, expected", [
    ("installed", True),
    (None, False),
    ("1.7.1", False),
    ("2.0.0", True),
])
def test_is_web_available_requires_pyjwt_2(monkeypatch, module, expected):
    if module != "installed":
        monkeypatch.setitem(sys.modules, "jwt", None if module is None else _fake_jwt(module))

    assert is_web_available() is expected


_MAIN_WEB_MESSAGE = """
import sys, types
fake = types.ModuleType("jwt")
fake.__version__ = "1.7.1"
sys.modules["jwt"] = fake
import volttron.platform.main as main
print(main.HAS_WEB)
print(main.web_unavailable_message())
"""


def test_platform_start_message_names_pyjwt_requirement():
    result = subprocess.run([sys.executable, "-c", _MAIN_WEB_MESSAGE],
                            capture_output=True, text=True, timeout=60)

    assert result.returncode == 0, result.stdout + result.stderr
    has_web, message = result.stdout.split("\n", 1)
    assert has_web == "False"
    assert "requires PyJWT 2, found 1.7.1" in message
    assert "bootstrap.py --web" in message

"""The RabbitMQ wildcard grant on CSR approval is only for federation links (CERT VU#173170.1, claim 2)."""

import pytest

pytest.importorskip("pika")

from volttron.platform.auth.auth_protocols.auth_rmq import is_federation_user  # noqa: E402


@pytest.mark.parametrize("user_id", ["remote.local.federation", "a.federation"])
def test_federation_link_user_is_recognised(user_id):
    assert is_federation_user(user_id)


@pytest.mark.parametrize("user_id", [
    "local.myfederationagent", "local.federation.agent", "federation", ".federation", "local.federationx",
    "local.Federation", "", None, 5,
])
def test_other_users_do_not_get_the_wildcard_grant(user_id):
    assert not is_federation_user(user_id)

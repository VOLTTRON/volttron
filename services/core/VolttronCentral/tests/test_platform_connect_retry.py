from unittest import mock

import gevent
import pytest

from services.core.VolttronCentral.volttroncentral.platforms import Platforms

TOPICS = ['platforms/vcp-one/status', 'platforms/vcp-one/iam/',
          'platforms/vcp-one/configure/']


class FakePubsub:
    """Records live subscriptions the way the bus would hold them."""

    def __init__(self):
        self.live = []

    def subscribe(self, peer, prefix, callback):
        self.live.append((prefix, callback))

    def unsubscribe(self, peer, prefix, callback):
        self.live.remove((prefix, callback))


def make_vc(fail_on_forward_number):
    """A VC whose platform answers every call, except forwarding request
    number `fail_on_forward_number` (1-based) which times out once."""
    vc = mock.Mock()
    vc.vip.pubsub = FakePubsub()
    forwards = []

    def call(identity, method, *args, **kwargs):
        result = mock.Mock()
        if method == 'subscribe_to_vcp':
            forwards.append(args)
            if len(forwards) == fail_on_forward_number:
                result.get.side_effect = gevent.Timeout(60)
                return result
        answers = {'get_instance_name': 'one',
                   'get_vip_addresses': ['tcp://127.0.0.1:22916'],
                   'get_devices': {}}
        result.get.return_value = answers.get(method)
        return result

    vc.vip.rpc.call.side_effect = call
    return vc


def live_prefixes(vc):
    return sorted(prefix for prefix, _ in vc.vip.pubsub.live)


def test_a_connect_that_fails_partway_leaves_no_subscription():
    vc = make_vc(fail_on_forward_number=2)
    platforms = Platforms(vc)

    with pytest.raises(gevent.Timeout):
        platforms.add_platform('vcp-one')

    assert live_prefixes(vc) == []
    assert platforms.get_platform_vip_identities() == set()


def test_a_retry_after_a_partial_connect_subscribes_each_topic_once():
    vc = make_vc(fail_on_forward_number=2)
    platforms = Platforms(vc)
    with pytest.raises(gevent.Timeout):
        platforms.add_platform('vcp-one')

    platforms.add_platform('vcp-one')

    assert live_prefixes(vc) == sorted(TOPICS)
    assert len(platforms.get_platform_vip_identities()) == 1


def test_a_failed_unsubscribe_does_not_hide_the_connect_failure():
    vc = make_vc(fail_on_forward_number=2)
    vc.vip.pubsub.unsubscribe = mock.Mock(side_effect=RuntimeError('gone'))

    with pytest.raises(gevent.Timeout):
        Platforms(vc).add_platform('vcp-one')

    assert vc.vip.pubsub.unsubscribe.call_count == 2

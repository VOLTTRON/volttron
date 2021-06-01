import logging
import subprocess
from typing import List

import gevent
import pytest
import tempfile
from dateutil.parser import parse as dateparse

from volttron.platform.messaging.health import STATUS_GOOD, STATUS_BAD, \
    STATUS_UNKNOWN
from volttron.platform.vip.agent import Agent, RPC
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform import jsonapi

logging.basicConfig(level=logging.DEBUG)
_log = logging.getLogger(__name__)


class ChannelSender(Agent):
    def __init__(self, **kwargs):
        super(ChannelSender, self).__init__(**kwargs)
        self.sent_data = None
        self.responses = []

    def do_send(self, peer, channel_name, data):
        _log.debug(f"Creating connection to {peer} using channel {channel_name}")
        # First create a channel and verify the connection
        channel = self.vip.channel.create(peer, channel_name)
        # Note no get at the end, because the greenlet should continue for
        # a while.
        _log.debug(f"Calling setup_channel on peer: {peer}")
        self.vip.rpc.call(peer, 'setup_channel', channel_name)
        with gevent.Timeout(10):
            resp = channel.recv()
            _log.debug(f"Sender got initial {resp}")
            self.responses.append(resp)
        
        # bytes are required to send across the zmq message bus.
        channel.send(data)
        with gevent.Timeout(10):
            resp = channel.recv()
            self.responses.append(resp)
        
        channel.close(linger=0)
        del channel

    def do_send_multipart(self, peer, chanel_name, mutliple_sends: List):
        pass


class ChannelReceiver(Agent):
    def __init__(self, **kwargs):
        super(ChannelReceiver, self).__init__(**kwargs)
        self.the_channel = None
        self.the_data = None

    @RPC.export
    def setup_channel(self, channel_name):
        """
        Start the processing of data coming through the channel.  For this
        test the sender will send data when we write to them the word
        send_it
        """
        # Prepare to install agent that is passed over to us.
        peer = self.vip.rpc.context.vip_message.peer
        _log.debug(f"Creating channel to peer {peer} named: {channel_name}")
        channel = self.vip.channel(peer, channel_name)
        _log.debug("Sending data back to peer contact.")
        channel.send(b'send_it')
        # channel.send('send_it')
        while True:
            # get the requested data
            with gevent.Timeout(10):
                self.the_data = channel.recv()

            if self.the_data:
                _log.debug(f"Receiver got the data {self.the_data}".encode('utf-8'))
                channel.send(f"got {self.the_data}".encode('utf-8'))
                gevent.sleep(0.1)
                break
        channel.close(linger=0)
        del channel


@pytest.mark.agent
def test_channel_send_data(volttron_instance):

    file = tempfile.NamedTemporaryFile(mode='wb')

    data = "x" * 50

    sender = volttron_instance.build_agent(agent_class=ChannelSender,
                                           identity="sender_agent", enable_channel=True)
    receiver = volttron_instance.build_agent(agent_class=ChannelReceiver,
                                             identity="receiver_agent", enable_channel=True)

    sender.do_send(peer=receiver.core.identity, data=data.encode('utf-8'), channel_name="foo_data")

    assert sender.responses
    assert receiver.the_data
    assert receiver.the_data == data.encode('utf-8')


@pytest.mark.agent
def test_agent_can_get_platform_version(volttron_instance):
    agent = volttron_instance.build_agent()
    query = Query(agent.core)
    response = subprocess.check_output(['volttron', "--version"],
                                       stderr=subprocess.STDOUT, universal_newlines=True)
    assert response.strip()
    _, version = response.strip().split(" ")

    platform_version = query.query("platform-version").get(timeout=2)
    assert version == platform_version


@pytest.mark.agent
def test_agent_status_set_when_created(volttron_instance):
    agent = volttron_instance.build_agent()
    assert agent.vip.health.get_status() is not None
    assert isinstance(agent.vip.health.get_status(), dict)
    l = agent.vip.health.get_status()
    assert l['status'] == STATUS_GOOD
    assert l['context'] is None

    assert isinstance(agent.vip.health.get_status_json(), str)
    l = jsonapi.loads(agent.vip.health.get_status_json())
    assert l['status'] == STATUS_GOOD
    assert l['context'] is None

    assert agent.vip.health.get_status_value() == STATUS_GOOD


@pytest.mark.agent
def test_agent_status_changes(volttron_instance):
    unknown_message = "This is unknown"
    bad_message = "Bad kitty"
    agent = volttron_instance.build_agent()
    agent.vip.health.set_status(STATUS_UNKNOWN, unknown_message)
    r = agent.vip.health.get_status()
    assert unknown_message == r['context']
    assert STATUS_UNKNOWN == r['status']

    agent.vip.health.set_status(STATUS_BAD, bad_message)
    r = agent.vip.health.get_status()
    assert bad_message == r['context']
    assert STATUS_BAD == r['status']


@pytest.mark.agent
def test_agent_last_update_increases(volttron_instance):
    agent = volttron_instance.build_agent()
    s = agent.vip.health.get_status()
    dt = dateparse(s['last_updated'], fuzzy=True)
    agent.vip.health.set_status(STATUS_UNKNOWN, 'Unknown now!')
    gevent.sleep(1)
    s = agent.vip.health.get_status()
    dt2 = dateparse(s['last_updated'], fuzzy=True)
    assert dt < dt2

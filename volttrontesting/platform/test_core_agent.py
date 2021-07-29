import hashlib
import logging
import subprocess
import tarfile              # For sending through a channel.
from typing import List

import gevent
import pytest
import os
from dateutil.parser import parse as dateparse

from volttron.platform.messaging.health import STATUS_GOOD, STATUS_BAD, \
    STATUS_UNKNOWN
from volttron.platform.vip.agent import Agent, RPC
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform import jsonapi
from volttrontesting.utils.platformwrapper import PlatformWrapper

logging.basicConfig(level=logging.DEBUG)
_log = logging.getLogger(__name__)


class ChannelSender(Agent):
    def __init__(self, **kwargs):
        super(ChannelSender, self).__init__(**kwargs)
        self.sent_data = None
        self.responses = []
        self.reciever_file_path = "/tmp/sentfile.tar"

    def send_file(self, to_peer, file_to_send):
        _log.debug(f"Sending file to peer {to_peer}")

        channel_name = "sending_file_channel"
        channel = self.vip.channel(to_peer, channel_name)

        _log.debug("Calling setup_send_file on receiver.")
        self.vip.rpc.call(to_peer, "setup_send_file", channel_name)
        gevent.sleep(0.5)
        _log.debug("After calling rpc method!")
        sha512 = hashlib.sha512()

        with open(file_to_send, "rb") as infile:
            first = True
            while True:
                with gevent.Timeout(120):
                    _log.debug("Attempting to read from channel")
                    # Protocol should be either a fetch or checksum
                    my_data = channel.recv()
                    op, size = jsonapi.loadb(my_data)
                    # op, size = channel.recv_multipart()
                    #_log.debug(f"Op size is {op} {size}")
                    if first:
                        first = False
                        if op != 'fetch':
                            channel.close(linger=0)
                            del channel
                            raise ValueError("Invalid protocol detected should be [b'fetch', size] where size is the amount of data to retrieve.")

                if op == 'fetch':
                    chunk = infile.read(size)
                    if chunk:
                        sha512.update(chunk)
                        # _log.debug(f"Sending chunk: {chunk}")
                        channel.send(chunk)
                    else:
                        channel.send(b'complete')
                        break
                elif op == 'checksum':
                    _log.debug(f"Sending checksum: {sha512.hexdigest()}")
                    channel.send(sha512.hexdigest().encode('utf-8'))

        _log.debug("Complete sending of file. Closing channel.")
        gevent.sleep(0.5)
        channel.close(linger=0)
        del channel

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


class ChannelReceiver(Agent):
    def __init__(self, **kwargs):
        super(ChannelReceiver, self).__init__(**kwargs)
        self.the_channel = None
        self.the_data = None
        self.receiver_file_path = "/tmp/myreceived.tar"
    
    @RPC.export
    def setup_send_file(self, channel_name):
        _log.debug("Setup send file executed!")
        BYTES_REQUESTED = 1024
        peer = self.vip.rpc.context.vip_message.peer
        _log.debug(f"Creating channel to peer {peer} named: {channel_name}")
        channel = self.vip.channel(peer, channel_name)
        _log.debug("Sending data back to peer contact.")
        
        make_fetch_request = jsonapi.dumpb(['fetch', BYTES_REQUESTED])
        make_checksum_request = jsonapi.dumpb(['checksum', ''])

        # channel.send(data_str) # .send_multipart(serialize_frames(['fetch', BYTES_REQUESTED]))
        # # channel.send(BYTES_REQUESTED)
        # data = channel.recv()
        # _log.debug(f"data received {len(data)}")

        with open(self.receiver_file_path, "wb") as fout:
            sha512 = hashlib.sha512()
            while True:
                _log.debug("Receiver sending fetch")
                channel.send(make_fetch_request)
                # chunk binary representation of the bytes read from
                # the other side of the connectoin
                chunk = channel.recv()
                if chunk == b'complete':
                    _log.debug("Completed file")
                    break
                _log.debug("Receiver sending checksum")
                channel.send(make_checksum_request)
                checksum = channel.recv()
                _log.debug(f"The checksum returned was: {checksum}")
                sha512.update(chunk)
                _log.debug(f"Received checksum: {checksum}")
                _log.debug(f"Expected checksum: {sha512.hexdigest()}")
                assert checksum.decode('utf-8') == sha512.hexdigest(), "Invalid checksum detected."
                fout.write(chunk)

        _log.debug("File completed!")
        channel.close(linger=0)
        del channel


    @RPC.export
    def setup_channel(self, channel_name):
        """
        Start the processing of data coming through the channel.  For this
        test the sender will send data when we write to them the word
        send_it
        """
        peer = self.vip.rpc.context.vip_message.peer
        _log.debug(f"Creating channel to peer {peer} named: {channel_name}")
        channel = self.vip.channel(peer, channel_name)
        gevent.sleep(0.1)
        _log.debug("Sending data back to peer contact.")
        channel.send(b'send_it')
        # channel.send('send_it')
        while True:

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
def test_channel_send_data(volttron_instance: PlatformWrapper):

    if not volttron_instance.messagebus == "zmq":
        pytest.skip("Channel only available for zmq message bus")
        return

    data = "x" * 50

    sender = volttron_instance.build_agent(agent_class=ChannelSender,
                                           identity="sender_agent", enable_channel=True)
    receiver = volttron_instance.build_agent(agent_class=ChannelReceiver,
                                             identity="receiver_agent", enable_channel=True)

    sender.do_send(peer=receiver.core.identity, data=data.encode('utf-8'), channel_name="foo_data")

    assert sender.responses
    assert receiver.the_data
    assert receiver.the_data == data.encode('utf-8')
    sender.core.stop()
    receiver.core.stop()


@pytest.mark.agent
def test_channel_send_file(volttron_instance: PlatformWrapper):

    if not volttron_instance.messagebus == "zmq":
        pytest.skip("Channel only available for zmq message bus")
        return

    # Create 
    with tarfile.open("/tmp/tmptar.tar", mode="w") as tf:
        for x in range(1, 50):
            with open(f"/tmp/data{x}", "w") as fin:
                fin.write("x" * 50)
            
            tf.add(f"/tmp/data{x}")

            os.remove(f"/tmp/data{x}")
    

    sender = volttron_instance.build_agent(agent_class=ChannelSender,
                                           identity="sender_agent", enable_channel=True)
    receiver = volttron_instance.build_agent(agent_class=ChannelReceiver,
                                             identity="receiver_agent", enable_channel=True)

    if os.path.exists(receiver.receiver_file_path):
        os.remove(receiver.receiver_file_path)

    sender.send_file(receiver.core.identity, "/tmp/tmptar.tar")

    assert os.path.isfile(receiver.receiver_file_path), f"Couldn't find file {receiver.receiver_file_path}"

    assert hashlib.sha256(open("/tmp/tmptar.tar", 'rb').read()).hexdigest() == hashlib.sha256(open(receiver.receiver_file_path, 'rb').read()).hexdigest() 

    sender.core.stop()
    receiver.core.stop()

@pytest.mark.agent
def test_agent_can_get_platform_version(volttron_instance):
    agent = volttron_instance.build_agent()
    query = Query(agent.core)
    response = subprocess.check_output(['volttron', "--version"],
                                       stderr=subprocess.STDOUT, universal_newlines=True)
    assert response.strip()
    _, version = response.strip().split(" ")

    platform_version = query.query("platform-version").get(timeout=2)
    assert str(version) == str(platform_version)


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
def test_agent_health_last_update_increases(volttron_instance):
    agent = volttron_instance.build_agent()
    s = agent.vip.health.get_status()
    dt = dateparse(s['last_updated'], fuzzy=True)
    agent.vip.health.set_status(STATUS_UNKNOWN, 'Unknown now!')
    gevent.sleep(1)
    s = agent.vip.health.get_status()
    dt2 = dateparse(s['last_updated'], fuzzy=True)
    assert dt < dt2

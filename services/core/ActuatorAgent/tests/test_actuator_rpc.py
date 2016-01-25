# pytest test cases for Actuator agent
from datetime import datetime, timedelta

import gevent
import gevent.subprocess as subprocess
import pytest
from gevent.subprocess import Popen
from mock import MagicMock
from volttron.platform.messaging import topics

TEST_AGENT = 'test-agent'


@pytest.fixture(scope="module")
def agent(request, volttron_instance1):
    # Create master driver config and 2 fake devices each with 6 points
    process = Popen(['python', 'config_builder.py', '--count=2', '--publish-only-depth-all',
                     'fake', 'fake6.csv', 'null'], env=volttron_instance1.env, cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print result
    assert result == 0

    # Start the master driver agent which would intern start the fake driver using the configs created above
    master_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/MasterDriverAgent",
            config_file="scripts/scalability-testing/configs/master-driver.agent",
            start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    # Start the actuator agent through which publish agent should communicate to fake device
    # Start the master driver agent which would intern start the fake driver using the configs created above
    actuator_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/ActuatorAgent",
            config_file="services/core/ActuatorAgent/tests/actuator.config",
            start=True)
    print("agent id: ", actuator_uuid)

    # 3: Start a fake agent to publish to message bus
    publish_agent = volttron_instance1.build_agent()
    # attach actuate method to publish_agent as it needs to be a class method
    publish_agent.actuate0 = MagicMock(name="mock_actuate0")

    # 4: add a tear down method to stop sqlhistorian agent and the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        volttron_instance1.stop_agent(actuator_uuid)
        volttron_instance1.stop_agent(master_uuid)
        publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return publish_agent


# def actuate0(self, peer, sender, bus,  topic, headers, message):
#     print("In actuate0")
#     print ("topic:",topic,'header:',headers,'message:',message)

# def actuate1(self, peer, sender, bus,  topic, headers, message):
#     print("In actuate1")
#     assert False
#     print ("topic:",topic,'header:',headers,'message:',message)
#     global TEST_AGENT
#     if headers[headers_mod.REQUESTER_ID] != TEST_AGENT:
#         return
#     result = self.vip.rpc.call(
#                'platform.actuator',                 # Target agent
#                'set_point',                         # Method
#                TEST_AGENT,                          # Requestor
#                'fakedriver1/SampleWritableFloat1',  # Point to set
#                '1.5'                                # New value
#                ).get(timeout=10)
#     if result == '1.5':
#         print("Set value correctly")




def test_actuate_schedule_announce(agent):
    announce = topics.ACTUATOR_SCHEDULE_ANNOUNCE(campus='', building='', unit='fakedriver0')
    agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix=announce,
                               callback=agent.actuate0)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=1))
    end = str(datetime.now() + timedelta(seconds=6))
    print ('start time for device0', start)
    msg = [
        ['fakedriver0', start, end]
    ]
    agent.actuate0 = MagicMock(name="magic_actuate0")
    result = agent.vip.rpc.call(
            'platform.actuator',
            'request_new_schedule',
            TEST_AGENT,
            'task1',
            'LOW',
            msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    assert result['result'] == 'SUCCESS'
    gevent.sleep(5)
    assert agent.actuate0.called == True
    assert agent.actuate0.call_count == 2
    args_list = agent.actuate0.call_args_list
    print ("***args_list", args_list)
    print ('***argslist of 0', args_list[0][0])
    print ('***argslist of 0', args_list[1][0])
    print ""
    i = 0
    while i < len(args_list[0][0]):
        print ("argsof ", i, args_list[0][0][i])
        i = i + 1

    gevent.sleep(5)
    print ("result is ", result)
    pass

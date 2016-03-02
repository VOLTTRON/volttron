import tempfile

import gevent
import os
import pytest
from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent import Agent


def validate_instances(wrapper1, wrapper2):
    assert wrapper1.bind_web_address
    assert wrapper2.bind_web_address
    assert wrapper1.bind_web_address != wrapper2.bind_web_address
    assert wrapper1.volttron_home
    assert wrapper2.volttron_home
    assert wrapper1.volttron_home != wrapper2.volttron_home


@pytest.mark.vc
def test_can_manage(vc_instance, pa_instance):
    vc_wrapper = vc_instance['wrapper']
    pa_wrapper = pa_instance['wrapper']

    validate_instances(vc_wrapper, pa_wrapper)

    tf = tempfile.NamedTemporaryFile()
    ks = KeyStore(tf.name)
    ks.generate()  #needed because using a temp file!!!!!
    print("connecting to vc instance with vip_adddress: {}".format(
        vc_wrapper.vip_address)
    )

    authfile = os.path.join(vc_wrapper.volttron_home, "auth.json")
    with open(authfile) as f:
        print("vc authfile: {}".format(f.read()))

    params = {
        "serverkey": vc_wrapper.publickey,
        "publickey": ks.public(),
        "secretkey": ks.secret()
    }
    print("PARAMS: {}".format(params))
    addr = "{}?serverkey={}&publickey={}&secretkey={}".format(
        vc_wrapper.vip_address[0],
        vc_wrapper.publickey,
        ks.public(),
        ks.secret()
    )

    # Create an agent to use for calling rpc methods on volttron.central.
    extagent= Agent(identity="external.agent", address=vc_wrapper.vip_address[0], **params)

    event = gevent.event.Event()
    gevent.spawn(extagent.core.run, event)#.join(0)
    event.wait(timeout=2)

    plist = extagent.vip.peerlist().get(timeout=2)
    assert "volttron.central" in plist

    retval = extagent.vip.rpc.call("volttron.central", "register_instance",
                          uri=pa_wrapper.bind_web_address,
                          display_name="hushpuppy").get(timeout=5)

    assert retval
    assert 'hushpuppy' == retval['display_name']
    assert retval['success']

    extagent.core.stop()

    # # build agent to interact with the vc agent on the vc_wrapper instance.
    # #agent = vc_wrapper.build_agent(**params)
    # # serverkey=vc_wrapper.publickey,
    # #                                publickey=ks.public(),
    # #                                secretkey=ks.secret())
    # with open(authfile) as f:
    #     print("vc authfile: {}".format(f.read()))
    # peers = agent.vip.peerlist().get(timeout=2)
    # assert "volttron.central" in peers



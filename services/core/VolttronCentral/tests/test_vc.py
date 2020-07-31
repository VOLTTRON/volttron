# import pytest
# import os
#
# from volttron.platform.web import DiscoveryInfo
# # noinspection PyUnresolvedReferences
# from vc_fixtures import vc_instance, vcp_instance, vc_and_vcp_together
#
# import gevent
#
#
# def test_platform_was_registered(vc_and_vcp_together):
#
#
# @pytest.mark.vc
# def test_publickey_retrieval(vc_instance, vcp_instance):
#     """ This method tests that the /discovery addresses.
#
#     The discovery now should return the server key for the bus as well as
#     for the volttron.central and platform.agent public keys if they are
#     available.
#
#     Parameters
#     ----------
#     :vc_instance:
#         A dictionary featuring a wrapper and ...
#     :vc_instance:
#         A dictionary featuring a wrapper and ...
#     """
#     vc_wrapper, vc_uuid, jsonrpc = vc_instance
#     pa_wrapper, pa_uuid = vcp_instance
#     gevent.sleep(1)
#
#     vc_info = DiscoveryInfo.request_discovery_info(
#         vc_wrapper.bind_web_address)
#     pa_info = DiscoveryInfo.request_discovery_info(
#         pa_wrapper.bind_web_address)
#
#     assert pa_info.serverkey
#     assert vc_info.serverkey
#     assert pa_info != vc_info.serverkey
#
#
# def onmessage(self, peer, sender, bus, topic, headers, message):
#     print('topic: {} message: {}'.format(topic, message))
#
#
# # @pytest.mark.vc
# # @pytest.mark.parametrize("display_name", [None, "happydays"])
# # def test_register_instance(vc_instance, pa_instance, display_name):
# #     vc_wrapper = vc_instance['wrapper']
# #     pa_wrapper = pa_instance['wrapper']
# #
# #     validate_instances(vc_wrapper, pa_wrapper)
# #
# #     print("connecting to vc instance with vip_adddress: {}".format(
# #         pa_wrapper.vip_address)
# #     )
# #
# #     controlagent = vc_wrapper.build_agent()
# #     controlagent.vip.pubsub.subscribe('', onmessage)
# #     controlagent.vip.rpc.call(
# #         'volttron.central', pa_wrapper.bind_web_address).get(timeout=5)
# #
# #     gevent.sleep(20)
#
#     # res = requests.get(pa_wrapper.bind_web_address+"/discovery/")
#     #
#     # assert res.ok
#     #
#     # viptcp = "{vip_address}?serverkey={serverkey}&secretkey
#     #
#     # authfile = os.path.join(vc_wrapper.volttron_home, "auth.json")
#     # with open(authfile) as f:
#     #     print("vc authfile: {}".format(f.read()))
#     #
#     # tf = tempfile.NamedTemporaryFile()
#     # paks = KeyStore(tf.name)
#     # paks.generate()  #needed because using a temp file!!!!
#     # print('Checking peers on pa using:\nserverkey: {}\npublickey: {}\n'
#     #       'secretkey: {}'.format(
#     #     pa_wrapper.publickey,
#     #     paks.public(),
#     #     paks.secret()
#     # ))
#     # paagent = pa_wrapper.build_agent(serverkey=pa_wrapper.publickey,
#     #                                  publickey=paks.public(),
#     #                                  secretkey=paks.secret())
#     # peers = paagent.vip.peerlist().get(timeout=3)
#     # assert "platform.agent" in peers
#     # paagent.core.stop()
#     # del paagent
#     #
#     # tf = tempfile.NamedTemporaryFile()
#     # ks = KeyStore(tf.name)
#     # ks.generate()  #needed because using a temp file!!!!!
#     # print('Checking peers on vc using:\nserverkey: {}\npublickey: {}\n'
#     #       'secretkey: {}'.format(
#     #     vc_wrapper.publickey,
#     #     ks.public(),
#     #     ks.secret()
#     # ))
#     #
#     # # Create an agent to use for calling rpc methods on volttron.central.
#     # controlagent = vc_wrapper.build_agent(serverkey=vc_wrapper.publickey,
#     #                                       publickey=ks.public(),
#     #                                       secretkey=ks.secret())
#     # plist = controlagent.vip.peerlist().get(timeout=2)
#     # assert "volttron.central" in plist
#     #
#     # print('Attempting to manage platform now.')
#     # print('display_name is now: ', display_name)
#     # dct = dict(peer="volttron.central", method="register_instance",
#     #                                     discovery_address=pa_wrapper.bind_web_address,
#     #                                     display_name=display_name)
#     # print(jsonapi.dumps(dct))
#     # if display_name:
#     #     retval = controlagent.vip.rpc.call("volttron.central", "register_instance",
#     #                                     discovery_address=pa_wrapper.bind_web_address,
#     #                                     display_name=display_name).get(timeout=10)
#     # else:
#     #
#     #     retval = controlagent.vip.rpc.call("volttron.central", "register_instance",
#     #                                     discovery_address=pa_wrapper.bind_web_address).get(timeout=10)
#     #
#     # assert retval
#     # if display_name:
#     #     assert display_name == retval['display_name']
#     # else:
#     #     assert pa_wrapper.bind_web_address == retval['display_name']
#     # assert retval['success']
#     #
#     # print('Testing that we now have a single entry in the platform_details')
#     # retval = controlagent.vip.rpc.call("volttron.central",
#     #                                    "list_platform_details").get(timeout=10)
#     # print("From vc list_platform_details: {}".format(retval))
#     #
#     # assert len(retval) == 1
#     # assert 'hushpuppy' == retval[0]['display_name']
#     # assert retval[0]['vip_address']
#     # assert not retval[0]['tags']
#     # assert retval[0]['serverkey']
#     #
#     # controlagent.core.stop()
#
#     # # build agent to interact with the vc agent on the vc_wrapper instance.
#     # #agent = vc_wrapper.build_agent(**params)
#     # # serverkey=vc_wrapper.publickey,
#     # #                                publickey=ks.public(),
#     # #                                secretkey=ks.secret())
#     # with open(authfile) as f:
#     #     print("vc authfile: {}".format(f.read()))
#     # peers = agent.vip.peerlist().get(timeout=2)
#     # assert "volttron.central" in peers
#

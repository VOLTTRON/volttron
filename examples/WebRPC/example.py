from volttronwebrpc import VolttronWebRPC

addr = "http://10.0.2.15:8080/jsonrpc"

volttron = VolttronWebRPC(addr, username='admin', password='admin')

topics = volttron.do_rpc('historian.get_topic_list')

fake_device_topics = [t for t in topics if t.startswith('fake')]

result = volttron.do_rpc('historian.query',
                         topic=fake_device_topics,
                         count=100,
                         order='LAST_TO_FIRST')

print result


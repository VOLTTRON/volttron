import pytest
from uuid import UUID
from volttron.platform.web.topic_tree import TopicNode, TopicTree, DeviceNode, DeviceTree


TOPIC_LIST = ['Campus/Building1/Fake1/SampleWritableFloat1', 'Campus/Building1/Fake1/SampleBool1',
              'Campus/Building2/Fake1/SampleWritableFloat1', 'Campus/Building2/Fake1/SampleBool1',
              'Campus/Building3/Fake1/SampleWritableFloat1', 'Campus/Building3/Fake1/SampleBool1']

ALL_IDENTIFIERS = ['root', 'root/Campus', 'root/Campus/Building1', 'root/Campus/Building1/Fake1',
                   'root/Campus/Building1/Fake1/SampleWritableFloat1', 'root/Campus/Building1/Fake1/SampleBool1',
                   'root/Campus/Building2', 'root/Campus/Building2/Fake1',
                   'root/Campus/Building2/Fake1/SampleWritableFloat1', 'root/Campus/Building2/Fake1/SampleBool1',
                   'root/Campus/Building3', 'root/Campus/Building3/Fake1',
                   'root/Campus/Building3/Fake1/SampleWritableFloat1', 'root/Campus/Building3/Fake1/SampleBool1']


def _is_valid_uuid(uuid_to_test):
    try:
        uuid_obj = UUID(uuid_to_test)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test


def test_topic_node_init():
    n = TopicNode()
    assert _is_valid_uuid(n.tag)
    assert _is_valid_uuid(n.identifier)
    assert n.expanded is True
    assert n.data is None
    assert n.segment_type == 'TOPIC_SEGMENT'
    assert n.topic == ''

    n = TopicNode(tag='foo', identifier='bar', expanded=False, data={'foo': 'bar'}, segment_type='OTHER',
                  topic='foo/bar')
    assert n.tag == 'foo'
    assert n.identifier == 'bar'
    assert n.expanded is False
    assert n.data == {'foo': 'bar'}
    assert n.segment_type == 'OTHER'
    assert n.topic == 'foo/bar'


@pytest.mark.parametrize('segment_type, expected', [('TOPIC_SEGMENT', True), ('TOPIC_ROOT', False), ('POINT', False),
                                                    ('DEVICE', False)])
def test_is_segment(segment_type, expected):
    n = TopicNode(segment_type=segment_type)
    assert n.is_segment() is expected


def test_topic_tree_init():
    t = TopicTree()
    assert len(t) == 1
    assert all([n.is_root() for n in t.all_nodes()])
    assert all([n.tag == 'root' and n.identifier == 'root' for n in t.all_nodes()])
    assert t.node_class == TopicNode
    assert all([isinstance(n, TopicNode) for n in t.all_nodes()])
    t = TopicTree(topic_list=TOPIC_LIST)
    assert len(t) == 14
    assert len(t.leaves()) == 6
    assert all([isinstance(n, TopicNode) for n in t.all_nodes()])


def test__from_topic_list():
    t = TopicTree()
    t.remove_node(t.root)
    t._from_topic_list(TOPIC_LIST, 'Campus')
    assert len(t) == 13
    assert t.get_node('Campus').segment_type == 'TOPIC_ROOT'
    buildings = ['Campus/Building1', 'Campus/Building2', 'Campus/Building3']
    assert all([t.get_node(n).segment_type == 'TOPIC_SEGMENT' for n in buildings])
    assert all([t.level(n) == 1 for n in buildings])
    devices = ['Campus/Building1/Fake1', 'Campus/Building2/Fake1', 'Campus/Building3/Fake1']
    assert all([t.get_node(n).segment_type == 'TOPIC_SEGMENT' for n in buildings])
    assert all([t.level(n) == 2 for n in devices])
    assert all([t.get_node(n).segment_type == 'TOPIC_SEGMENT' for n in TOPIC_LIST])
    assert all([t.level(n) == 3 for n in TOPIC_LIST])
    assert all([top[7:] in [n.topic for n in t.leaves()] for top in TOPIC_LIST])
    assert TOPIC_LIST == [n.identifier for n in t.leaves()]
    # Test duplicates ignored:
    t.remove_node(t.root)
    t._from_topic_list(TOPIC_LIST + ['Campus/Building1/Fake1/SampleBool1'], 'Campus')
    assert len(t) == 13


def test_add_node():
    t = TopicTree()
    n = TopicNode(tag='foo', identifier='bar')
    t.add_node(n, t.root)
    assert len(t) == 2
    assert t.level('bar') == 1
    assert t.parent('bar') is t.get_node(t.root)


def test_get_children_dict():
    t = TopicTree(topic_list=TOPIC_LIST)
    # Test response to single sub_root__node_id
    kids = t.get_children_dict('root/Campus/Building1/Fake1')
    assert kids == {'SampleWritableFloat1': '/root/Campus/Building1/Fake1/SampleWritableFloat1',
                    'SampleBool1': '/root/Campus/Building1/Fake1/SampleBool1'}
    # Test response to multiple sub_root__node_ids
    kids = t.get_children_dict(['root/Campus/Building1/Fake1', 'root/Campus/Building1'])
    assert kids == {'SampleWritableFloat1': '/root/Campus/Building1/Fake1/SampleWritableFloat1',
                    'SampleBool1': '/root/Campus/Building1/Fake1/SampleBool1',
                    'Fake1': '/root/Campus/Building1/Fake1'}
    # Test include_root == True
    assert all([v[:6] == '/root/' for v in kids.values()])
    # Test include_root == False
    kids = t.get_children_dict(['root/Campus/Building1/Fake1', 'root/Campus/Building1'], include_root=False)
    assert all('root' not in v for v in kids.values())
    # Test with prefix:
    kids = t.get_children_dict(['root/Campus/Building1/Fake1', 'root/Campus/Building1'], prefix='/foo/bar')
    assert all([v[:14] == '/foo/bar/root/' for v in kids.values()])
    # Test replace topic:
    kids = t.get_children_dict(['root/Campus/Building1/Fake1', 'root/Campus/Building1'], replace_topic='foo/bar')
    assert kids == {'SampleWritableFloat1': '/root/foo/bar/SampleWritableFloat1',
                    'SampleBool1': '/root/foo/bar/SampleBool1',
                    'Fake1': '/root/foo/bar/Fake1'}


def test_get_matches():
    t = TopicTree(TOPIC_LIST)
    nodes = [t.get_node('root/Campus/Building1/Fake1/SampleWritableFloat1'),
             t.get_node('root/Campus/Building1/Fake1/SampleBool1')]
    assert nodes == t.get_matches('root/Campus/Building1/Fake1/-')
    # Test return_nodes == False
    idents = ['root/Campus/Building1/Fake1/SampleWritableFloat1', 'root/Campus/Building1/Fake1/SampleBool1']
    assert idents == t.get_matches('root/Campus/Building1/Fake1/-', return_nodes=False)


@pytest.mark.parametrize('topic_pattern, regex, exact_matches, included',
    [
        ('', '', [], ALL_IDENTIFIERS),
        ('root/Campus/Building1/Fake1/-', '', [],
         ['root', 'root/Campus', 'root/Campus/Building1', 'root/Campus/Building1/Fake1',
          'root/Campus/Building1/Fake1/SampleWritableFloat1', 'root/Campus/Building1/Fake1/SampleBool1']),
        ('', '.*Bool.*', [],
         ['root', 'root/Campus', 'root/Campus/Building1', 'root/Campus/Building1/Fake1',
          'root/Campus/Building1/Fake1/SampleBool1', 'root/Campus/Building2', 'root/Campus/Building2/Fake1',
          'root/Campus/Building2/Fake1/SampleBool1', 'root/Campus/Building3', 'root/Campus/Building3/Fake1',
          'root/Campus/Building3/Fake1/SampleBool1']),
        ('root/Campus/Building1/Fake1/-', '.*Bool.*', [],
         ['root', 'root/Campus', 'root/Campus/Building1', 'root/Campus/Building1/Fake1',
          'root/Campus/Building1/Fake1/SampleBool1']),
        ('', '', ['root/Campus/Building1/Fake1/SampleBool1', 'root/Campus/Building1/Fake1/SampleWritableFloat1',
                  'root/Campus/Building3'],
         ['root', 'root/Campus', 'root/Campus/Building1', 'root/Campus/Building1/Fake1',
          'root/Campus/Building1/Fake1/SampleBool1', 'root/Campus/Building1/Fake1/SampleWritableFloat1',
          'root/Campus/Building3']),
        ('', '.*(Building1|Building3).*', [],
         ['root', 'root/Campus', 'root/Campus/Building1', 'root/Campus/Building1/Fake1',
          'root/Campus/Building1/Fake1/SampleBool1', 'root/Campus/Building1/Fake1/SampleWritableFloat1',
          'root/Campus/Building3', 'root/Campus/Building3/Fake1', 'root/Campus/Building3/Fake1/SampleBool1',
          'root/Campus/Building3/Fake1/SampleWritableFloat1']),
        ('', '.*(Building1|Building3).*', ['root/Campus/Building1/Fake1/SampleWritableFloat1'],
         ['root', 'root/Campus', 'root/Campus/Building1', 'root/Campus/Building1/Fake1',
          'root/Campus/Building1/Fake1/SampleWritableFloat1'])
    ]
)
def test_prune(topic_pattern, regex, exact_matches, included):
    excluded = [i for i in ALL_IDENTIFIERS if i not in included]
    t = TopicTree(TOPIC_LIST)
    pruned = t.prune(topic_pattern=topic_pattern, regex=regex, exact_matches=exact_matches)
    assert isinstance(pruned, TopicTree)
    assert all([n.identifier in included for n in pruned.all_nodes()])
    assert all([n.identifier not in excluded for n in pruned.all_nodes()])
    assert [n.segment_type == t.get_node(n.identifier) for n in pruned.all_nodes()]
    assert [n.data == t.get_node(n.data) for n in pruned.all_nodes()]


def test_prune_final_segments():
    t = TopicTree(TOPIC_LIST + ['Campus/Building1/Fake1/EKG', 'Campus/Building1/Fake1/EKG_Sin',
                                'Campus/Building1/Fake1/EKG_Cos'])
    pruned = t.prune(topic_pattern='root/Campus/Building1/Fake1/EKG')
    included = ['root', 'root/Campus', 'root/Campus/Building1', 'root/Campus/Building1/Fake1',
                'root/Campus/Building1/Fake1/EKG']
    assert [n.identifier for n in pruned.all_nodes()] == included
    
    
def test_device_node_init():
    n = DeviceNode()
    assert _is_valid_uuid(n.tag)
    assert _is_valid_uuid(n.identifier)
    assert n.expanded is True
    assert n.data is None
    assert n.segment_type == 'TOPIC_SEGMENT'
    assert n.topic == ''

    n = DeviceNode(tag='foo', identifier='bar', expanded=False, data={'foo': 'bar'}, segment_type='OTHER',
                   topic='foo/bar')
    assert n.tag == 'foo'
    assert n.identifier == 'bar'
    assert n.expanded is False
    assert n.data == {'foo': 'bar'}
    assert n.segment_type == 'OTHER'
    assert n.topic == 'foo/bar'


@pytest.mark.parametrize('segment_type, expected', [('TOPIC_SEGMENT', False), ('TOPIC_ROOT', False), ('POINT', False),
                                                    ('DEVICE', True)])
def test_is_device(segment_type, expected):
    n = DeviceNode(segment_type=segment_type)
    assert n.is_device() is expected


@pytest.mark.parametrize('segment_type, expected', [('TOPIC_SEGMENT', False), ('TOPIC_ROOT', False), ('POINT', True),
                                                    ('DEVICE', False)])
def test_is_point(segment_type, expected):
    n = DeviceNode(segment_type=segment_type)
    assert n.is_point() is expected


def test_device_tree_init():
    t = DeviceTree()
    assert len(t) == 1
    assert all([n.is_root() for n in t.all_nodes()])
    assert all([n.tag == 'devices' and n.identifier == 'devices' for n in t.all_nodes()])
    assert t.node_class == DeviceNode
    assert all([isinstance(n, DeviceNode) for n in t.all_nodes()])
    t = DeviceTree(topic_list=TOPIC_LIST)
    assert len(t) == 14
    assert len(t.leaves()) == 6
    assert all([isinstance(n, DeviceNode) for n in t.all_nodes()])
    assert t.get_node(t.root).identifier == 'devices'
    t = DeviceTree(topic_list=TOPIC_LIST, assume_full_topics=True)
    assert all([n.segment_type == 'POINT' for n in t.leaves()])
    assert all([t.parent(n.identifier).segment_type == 'DEVICE' for n in t.leaves()])


@pytest.mark.parametrize(
    'nid, expected',
    [
        (None, ['devices/Campus/Building1/Fake1', 'devices/Campus/Building2/Fake1',
                'devices/Campus/Building3/Fake1']),
        ('devices/Campus/Building2', ['devices/Campus/Building2/Fake1'])
    ])
def test_devices(nid, expected):
    t = DeviceTree(topic_list=TOPIC_LIST, assume_full_topics=True)
    assert [n.identifier for n in t.devices(nid)] == expected


def _mock_rpc_caller(peer, method, agent, file_name=None, raw=False, external_platform=None):
    if method == 'list_configs':
        return ['config', 'devices/Campus/Building1/Fake1', 'devices/Campus/Building2/Fake1',
                'devices/Campus/Building3/Fake1', 'registry_configs/fake.csv']
    elif method == 'get_config' and '.csv' in file_name:
        return [{'Point Name': 'SampleBool1',  'Volttron Point Name': 'SampleBool1',  'Units': 'On / Off',
                 'Units Details': 'on/off',  'Writable': 'FALSE',  'Starting Value': 'TRUE',  'Type': 'boolean',
                 'Notes': 'Status indidcator of cooling stage 1'},
                {'Point Name': 'SampleWritableFloat1', 'Volttron Point Name': 'SampleWritableFloat1',  'Units': 'PPM',
                 'Units Details': '1000.00 (default)',  'Writable': 'TRUE',  'Starting Value': '10',  'Type': 'float',
                 'Notes': 'Setpoint to enable demand control ventilation'}]
    elif method == 'get_config' and '.csv' not in file_name:
        return {'driver_config': {},  'registry_config': 'config://registry_configs/fake.csv', 'interval': 60,
                'timezone': 'US/Pacific', 'driver_type': 'fakedriver', 'publish_breadth_first_all': False,
                'publish_depth_first': False, 'publish_breadth_first': False, 'campus': 'campus',
                'building': 'building', 'unit': 'fake_device'}
    else:
        return None


_mock_rpc_caller.__repr__ = lambda: 'VUIEndpoints'


def test_from_store():
    t = DeviceTree.from_store('my_instance_name', _mock_rpc_caller)
    assert len(t) == 14
    assert len(t.leaves()) == 6
    assert all([isinstance(n, DeviceNode) for n in t.all_nodes()])
    assert t.get_node(t.root).identifier == 'devices'
    t = DeviceTree(topic_list=TOPIC_LIST, assume_full_topics=True)
    assert all([n.segment_type == 'POINT' for n in t.leaves()])
    assert all([t.parent(n.identifier).segment_type == 'DEVICE' for n in t.leaves()])
    assert all([n.data == {'Point Name': 'SampleBool1', 'Units': 'On / Off', 'Units Details': 'on/off',
                           'Writable': 'FALSE',  'Starting Value': 'TRUE',  'Type': 'boolean',
                           'Notes': 'Status indidcator of cooling stage 1'}
                for n in t.get_matches('Campus/-/Fake1/SampleBool1')])
    assert all([n.data == {'Point Name': 'SampleWritableFloat1', 'Units': 'PPM', 'Units Details': '1000.00 (default)',
                           'Writable': 'TRUE', 'Starting Value': '10',  'Type': 'float',
                           'Notes': 'Setpoint to enable demand control ventilation'}
                for n in t.get_matches('Campus/-/Fake1/SampleWritableFloat1')])
    assert all(n.data == {'driver_config': {},  'registry_config': 'config://registry_configs/fake.csv', 'interval': 60,
                          'timezone': 'US/Pacific', 'driver_type': 'fakedriver', 'publish_breadth_first_all': False,
                          'publish_depth_first': False, 'publish_breadth_first': False, 'campus': 'campus',
                          'building': 'building', 'unit': 'fake_device'}
               for n in t.get_matches('Campus/-/Fake1'))


@pytest.mark.parametrize(
    'nid, expected',
    [
        (None, ['devices/Campus/Building1/Fake1/SampleWritableFloat1',
                'devices/Campus/Building1/Fake1/SampleBool1',
                'devices/Campus/Building2/Fake1/SampleWritableFloat1',
                'devices/Campus/Building2/Fake1/SampleBool1',
                'devices/Campus/Building3/Fake1/SampleWritableFloat1',
                'devices/Campus/Building3/Fake1/SampleBool1']),
        ('devices/Campus/Building2',
         ['devices/Campus/Building2/Fake1/SampleBool1',
          'devices/Campus/Building2/Fake1/SampleWritableFloat1'])
    ])
def test_points(nid, expected):
    t = DeviceTree(topic_list=TOPIC_LIST, assume_full_topics=True)
    assert [n.identifier for n in t.points(nid)] == expected

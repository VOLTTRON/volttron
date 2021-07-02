# TODO: Add treelib to requirements.
from copy import deepcopy
from typing import Union, Iterable
from treelib import Tree, Node
from treelib.exceptions import DuplicatedNodeIdError, NodeIDAbsentError
from collections import defaultdict

from volttron.platform.agent.known_identities import CONFIGURATION_STORE

import re
from os.path import normpath

import logging
_log = logging.getLogger(__name__)


class TopicNode(Node):
    def __init__(self, tag=None, identifier=None, expanded=True, data=None, segment_type='TOPIC_SEGMENT', topic=''):
        super(TopicNode, self).__init__(tag, identifier, expanded, data)
        self.segment_type = segment_type
        self.topic = topic

    def is_segment(self):
        return True if self.segment_type == 'TOPIC_SEGMENT' else False


class TopicTree(Tree):
    def __init__(self, topic_list=None, root_name='root', node_class=None, *args, **kwargs):
        node_class = node_class if node_class else TopicNode
        super(TopicTree, self).__init__(node_class=node_class, *args, **kwargs)
        if topic_list:
            self._from_topic_list(topic_list, root_name)
        else:
            self.create_node(root_name, root_name).segment_type = 'TOPIC_ROOT'

    def _from_topic_list(self, topic_list, root_name):
        tops = [t.split('/') for t in topic_list]
        if all([top[0] == root_name for top in tops]):
            [top.pop(0) for top in tops]
        self.create_node(root_name, root_name).segment_type = 'TOPIC_ROOT'
        for top in tops:
            parent = root_name
            for segment in top:
                nid = '/'.join([parent, segment])
                try:
                    self.create_node(segment, nid, parent=parent)
                except DuplicatedNodeIdError:
                    pass
                parent = nid

    def add_node(self, node, parent=None):
        super(TopicTree, self).add_node(node, parent)
        node.topic = node.identifier[(len(self.root) + 1):]
        return node

    # TODO: Should this actually be get_child_topics() where topics or routes are returned with wildcards?
    def get_children_dict(self, sub_root_node_id: Union[list, str], include_root: bool = True,
                          prefix: str = '', replace_topic: str = None) -> dict:
        sub_root_node_id = sub_root_node_id if type(sub_root_node_id) is list else [sub_root_node_id]
        level_dict = defaultdict(set)
        for r_id in sub_root_node_id:
            for d in self.children(r_id):
                try:
                    if replace_topic:
                        if include_root:
                            level_dict[d.tag].add('/'.join([self.root, replace_topic, d.tag]))
                        else:
                            level_dict[d.tag].add('/'.join([replace_topic, d.tag]))
                    else:
                        if include_root:
                            level_dict[d.tag].add(d.identifier)
                        else:
                            level_dict[d.tag].add(d.identifier.split('/', 1)[1])
                except NodeIDAbsentError as e:
                    return {}
        ret_dict = {}
        for k, s in level_dict.items():
            if len(s) > 1:
                ret_dict[k] = sorted([normpath('/'.join([prefix, v])) for v in s])
            else:
                ret_dict[k] = normpath('/'.join([prefix, s.pop()]))
        return ret_dict

    def prune(self, topic_pattern: str = None, regex: str = None, exact_matches: Iterable = None, *args, **kwargs):
        if topic_pattern:
            pattern = re.compile(topic_pattern.replace('-', '[^/]+'))
            nids = [n.identifier for n in self.filter_nodes(lambda x: pattern.search(x.identifier))]
        else:
            nids = list(self.expand_tree())
        if regex:
            regex = re.compile(regex)
            nids = [n for n in nids if regex.search(n)]
        if exact_matches:
            nids = [n for n in nids if n in exact_matches]
        pruned = self.__class__(topic_list=nids, root_name=self.root, *args, **kwargs)
        for nid in [n.identifier for n in pruned.all_nodes()]:
            old = self.get_node(nid)
            pruned.update_node(nid, data=old.data, segment_type=old.segment_type)
        return pruned

    def get_matches(self, topic, return_nodes=True):
        pattern = topic.replace('-', '[^/]+') + '$'
        nodes = self.filter_nodes(lambda x: re.match(pattern, x.identifier))
        if return_nodes:
            return list(nodes)
        else:
            return [n.identifier for n in nodes]


class DeviceNode(TopicNode):
    def __init__(self, tag=None, identifier=None, expanded=True, data=None, segment_type='TOPIC_SEGMENT'):
        super(DeviceNode, self).__init__(tag, identifier, expanded, data, segment_type)

    def is_point(self):
        return True if self.segment_type == 'POINT' else False

    def is_device(self):
        return True if self.segment_type == 'DEVICE' else False


class DeviceTree(TopicTree):
    def __init__(self, topic_list=None, root_name='devices', *args, **kwargs):
        super(DeviceTree, self).__init__(topic_list=topic_list, root_name=root_name, node_class=DeviceNode,
                                         *args, **kwargs)

    def points(self, nid=None):
        if nid is None:
            points = [n for n in self._nodes.values() if n.is_point()]
        else:
            points = [self[n] for n in self.expand_tree(nid) if self[n].is_point()]
        return points

    def devices(self, nid=None):
        if nid is None:
            points = [n for n in self._nodes.values() if n.is_device()]
        else:
            points = [self[n] for n in self.expand_tree(nid) if self[n].is_device()]
        return points

    # TODO: Getting points requires getting device config, using it to find the registry config,
    #  and then parsing that. There is not a method in config.store, nor in the platform.driver for
    #  getting a completed configuration. The configuration is only fully assembled in the subsystem's
    #  _initial_update method called when the agent itself calls get_configs at startup. There does not
    #  seem to be an equivalent management method, and the code for this is in the agent subsystem
    #  rather than the service (though it is reached through the service, oddly...
    @classmethod
    def from_store(cls, platform, rpc_caller):
        # TODO: This is a little hackish. Perhaps VUIEndpoints._rpc should use "external_platform" instead of
        #  "on_platform"?
        kwargs = {'on_platform': platform} if 'VUIEndpoints' in rpc_caller.__repr__() else {}
        devices = rpc_caller(CONFIGURATION_STORE, 'manage_list_configs', 'platform.driver', **kwargs)
        devices = devices if kwargs else devices.get(timeout=5)
        devices = [d for d in devices if re.match('^devices/.*', d)]
        device_tree = cls(devices)
        for d in devices:
            dev_config = rpc_caller(CONFIGURATION_STORE, 'manage_get', 'platform.driver', d, raw=False, **kwargs)
            dev_config = dev_config if kwargs else dev_config.get(timeout=5)
            reg_cfg_name = dev_config.pop('registry_config')[len('config://'):]
            device_tree.update_node(d, data=dev_config, segment_type='DEVICE')
            registry_config = rpc_caller('config.store', 'manage_get', 'platform.driver',
                                         f'{reg_cfg_name}', raw=False, **kwargs)
            registry_config = registry_config if kwargs else registry_config.get(timeout=5)
            for pnt in registry_config:
                point_name = pnt.pop('Volttron Point Name')
                n = device_tree.create_node(point_name, f"{d}/{point_name}", parent=d, data=pnt)
                n.segment_type = 'POINT'
        return device_tree

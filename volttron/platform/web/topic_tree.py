# TODO: Add treelib to requirements.
from typing import Union
from treelib import Tree
from treelib.exceptions import DuplicatedNodeIdError, NodeIDAbsentError
from collections import defaultdict

import re
from os.path import normpath

import logging
_log = logging.getLogger(__name__)


class TopicTree(Tree):
    def __init__(self, topic_list=None, root_name='root', *args, **kwargs):
        super(TopicTree, self).__init__(*args, **kwargs)
        self.from_topic_list(topic_list, root_name) if topic_list else Tree(*args, **kwargs)

    def from_topic_list(self, topic_list, root_name):
        tops = [t.split('/') for t in topic_list]
        if all([top[0] == root_name for top in tops]):
            [top.pop(0) for top in tops]
        self.create_node(root_name, root_name)
        for top in tops:
            parent = root_name
            for segment in top:
                nid = '/'.join([parent, segment])
                try:
                    self.create_node(segment, nid, parent=parent)
                except DuplicatedNodeIdError:
                    pass
                parent = nid

    def get_children_dict(self, sub_root_node_id: Union[list, str], include_root: bool = True,
                          prefix: str = '', replace_topic: str = None) -> dict:
        _log.debug(f'VUI TopicTree; In get_children_dict, sub_root_node_id: {sub_root_node_id},'
                   f' include_root: {include_root}, prefix: {prefix}')
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
                    _log.debug(f'VUI TopicTree: In NodeIDAbsentError Exception block: {e}')
                    return {}
        ret_dict = {}
        for k, s in level_dict.items():
            if len(s) > 1:
                ret_dict[k] = sorted([normpath('/'.join([prefix, v])) for v in s])
            else:
                ret_dict[k] = normpath('/'.join([prefix, s.pop()]))
        return ret_dict

    def prune_to_topic(self, topic, tree=None):
        _log.debug(f'VUI TopicTree: in prune_to_topic(), topic is: {topic}')
        try:
            tree = tree if tree else self
            tree = TopicTree(tree=tree.subtree(tree.root), deep=True)
            nid = tree.root
            for s in [s for s in topic.split('/') if s]:
                if s != '-':
                    nid = f'{nid}/{s}'
                    for s in tree.siblings(nid):
                        tree.remove_node(s.identifier)
                else:
                    topic_parts = topic.split('-/', 1)
                    was_leaf = tree.get_node(nid).is_leaf()
                    for successor in tree.children(nid):
                        subtopic = topic_parts[1] if len(topic_parts) > 1 else ''
                        tree.paste(tree.parent(successor.identifier).identifier,
                                   self.prune_to_topic(subtopic, tree.remove_subtree(successor.identifier)))
                    if was_leaf == bool(tree.children(nid)):
                        tree.remove_node(nid)
                    return tree
        except NodeIDAbsentError:
            return TopicTree()
        return tree

    def get_matches(self, topic, return_nodes=True):
        _log.debug('VUI TopicTree: in get_matches()')
        pattern = topic.replace('-', '[^/]+') + '$'
        nodes = self.filter_nodes(lambda x: re.match(pattern, x.identifier))
        if return_nodes:
            return list(nodes)
        else:
            return [n.identifier for n in nodes]


class DeviceTree(TopicTree):
    def __init__(self, topic_list=None, root_name='devices', *args, **kwargs):
        super(DeviceTree, self).__init__(self, topic_list=None, root_name='devices', *args, **kwargs)

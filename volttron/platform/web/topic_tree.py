# TODO: Add treelib to requirements.
from typing import Union
from treelib import Tree
from treelib.exceptions import DuplicatedNodeIdError, NodeIDAbsentError

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

    # TODO: Handle multiple sub_root_node_ids.
    def get_children_dict(self, sub_root_node_id: Union[list, str], include_root: bool = True,
                          prefix: str = None, replace_topic: str = None) -> dict:
        _log.debug(f'VUI TopicTree; In get_children_dict, sub_root_node_id: {sub_root_node_id},'
                   f' include_root: {include_root}, prefix: {prefix}')
        sub_root_node_id = sub_root_node_id if type(sub_root_node_id) is list else [sub_root_node_id]
        level_dict = {}
        for r_id in sub_root_node_id:
            try:

                if include_root and replace_topic:
                    l_dict = {d.tag: '/'.join([self.root, replace_topic, d.tag]) for d in self.children(r_id)}
                elif include_root and not replace_topic:
                    l_dict = {d.tag: d.identifier for d in self.children(r_id)}
                elif not include_root and replace_topic:
                    l_dict = {d.tag: '/'.join([replace_topic, d.tag]) for d in self.children(r_id)}
                else:
                    l_dict = {d.tag: d.identifier.split('/', 1)[1] for d in self.children(r_id)}
                if prefix:
                    l_dict = {k: normpath('/'.join([prefix, v])) for k,v in l_dict.items()}
                level_dict.update(l_dict)
            except NodeIDAbsentError as e:
                _log.debug(f'VUI TopicTree: In NodeIDAbsentError Exception block: {e}')
                return {}
        return level_dict

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
                    for successor in tree.children(nid):
                        subtopic = topic_parts[1] if len(topic_parts) > 1 else ''
                        tree.paste(tree.parent(successor.identifier).identifier,
                                   self.prune_to_topic(subtopic, tree.remove_subtree(successor.identifier)))
                    return tree
        except NodeIDAbsentError:
            return TopicTree()
        return tree

    # TODO: Does not seem to work when last segment is /- nor /-/'
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

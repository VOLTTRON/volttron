# TODO: Add treelib to requirements.
from treelib import Tree
from treelib.exceptions import DuplicatedNodeIdError, NodeIDAbsentError

from os.path import normpath

import logging
_log = logging.getLogger(__name__)


class TopicTree(Tree):
    def __init__(self, topic_list=None, root_name='root', *args, **kwargs):
        super(TopicTree, self).__init__(*args, **kwargs)
        self.from_topic_list(topic_list, root_name) if topic_list else Tree()

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

    def get_children_dict(self, sub_root_node_id: str, include_root: bool = True, prefix: str = None) -> dict:
        _log.debug(f'In get_children_dict, sub_root_node_id: {sub_root_node_id}, include_root: {include_root}, prefix: {prefix}')
        try:
            if include_root:
                level_dict = {d.tag: d.identifier for d in self.children(sub_root_node_id)}
                _log.debug(f'level_dict in include_root block is: {level_dict}')
            else:
                level_dict = {d.tag: d.identifier.split('/', 1)[1] for d in self.children(sub_root_node_id)}
            if prefix:
                level_dict = {k: normpath('/'.join([prefix, v])) for k,v in level_dict.items()}
        except NodeIDAbsentError as e:
            _log.debug(f'In NodeIDAbsentError Exception block: {e}')
            return {}
        return level_dict

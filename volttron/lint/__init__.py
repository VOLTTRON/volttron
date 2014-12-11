
import os

from astroid import MANAGER, nodes
from astroid.builder import AstroidBuilder


def transform(module):
    dirname = os.path.dirname(__file__)
    path = os.path.join(dirname, module.name + '.py')
    if not os.path.exists(path):
        return
    fake = AstroidBuilder(MANAGER).file_build(path)
    module.locals.update(fake.locals)


def register(linter):
    MANAGER.register_transform(nodes.Module, transform)

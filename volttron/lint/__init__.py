
import os

from astroid import MANAGER, nodes
from astroid.builder import AstroidBuilder


def transform(module):
    #print 'transform', module.name
    dirname = os.path.dirname(__file__)
    path = os.path.join(dirname, module.name + '.py')
    if not os.path.exists(path):
        return
    #print 'faking', module.name
    fake = AstroidBuilder(MANAGER).file_build(path)
    for name, obj in fake.locals.iteritems():
        try:
            objlist = module.locals[name]
        except KeyError:
            module.locals[name] = obj
        else:
            objlist.extend(obj)


def register(linter):
    MANAGER.register_transform(nodes.Module, transform)

# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

'''
volttron.lint -- a pylint plugin to mask spurious dynamic attribute errors.

volttron.lint is a pylint plugin to mask spurious errors produced by pylint
when objects with dynamic attributes are used. Dynamic attributes are those not
defined directly on the object but are instead added by a metaclass or through
calls to __getattribute__(). This module allows adding fake modules/classes
which are added to the lookup mechanism to allow pylint to properly check
dynamic attributes.

Each fake module should be contained in a file in this directory named the same
as the module it fakes plus a '.py' extension. Upon loading the plugin, a
module transform function will be registered which will read the module file,
if it exists, and create and add the appropriate objects and attributes to the
namespace for that class. See the existing files for details.
'''

import os

from astroid import MANAGER, nodes
from astroid.builder import AstroidBuilder


def transform(module):
    '''Add fake locals to a module's namespace.'''
    # Generate the path to the fake module
    dirname = os.path.dirname(__file__)
    path = os.path.join(dirname, module.name + '.py')
    if not os.path.exists(path):
        return
    # If the file exists, add fakes to the module's namespace
    fake = AstroidBuilder(MANAGER).file_build(path)
    for name, obj in fake.locals.items():
        module.locals.setdefault(name, []).extend(obj)


def register(linter):
    '''Register the transform function during plugin registration.'''
    MANAGER.register_transform(nodes.Module, transform)

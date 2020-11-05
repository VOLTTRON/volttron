# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}



import functools
from types import MethodType

import gevent


__all__ = ['annotate', 'annotations', 'dualmethod', 'spawn']


def annotate(obj, kind, name, value):
    # pylint: disable=protected-access
    try:
        annotations = obj._annotations
    except AttributeError:
        obj._annotations = annotations = {}
    try:
        items = annotations[name]
    except KeyError:
        annotations[name] = items = kind()
    assert isinstance(items, kind)
    try:
        add = items.add
    except AttributeError:
        try:
            add = items.append
        except AttributeError:
            try:
                add = items.update
            except AttributeError:
                items += value
                return
    add(value)


def annotations(obj, kind, name):
    # pylint: disable=protected-access
    try:
        annotations = obj._annotations
    except AttributeError:
        annotations = {}
    try:
        items = annotations[name]
    except KeyError:
        items = kind()
    assert isinstance(items, kind)
    return items


def spawn(method):
    '''Run a decorated method in its own greenlet, which is returned.'''
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        return gevent.spawn(method, *args, **kwargs)
    return wrapper


class dualmethod(object):
    '''Descriptor to allow class and instance methods of the same name.

    This class implements a descriptor that works similar to the
    classmethod() built-ins and can be used as a decorator, like the
    property() built-in. Instead of a method being only a class or
    instance method, two methods can share the same name and be accessed
    as an instance method or a class method based on the context.

    Example:

    >>> class Foo(object):
    ...     @dualmethod
    ...     def bar(self):
    ...         print('instance method for', self)
    ...     @bar.classmethod
    ...     def bar(cls):
    ...         print('class method for', cls)
    ...
    >>> Foo.bar()
    class method for <class '__main__.Foo'>
    >>> Foo().bar()
    instance method for <__main__.Foo object at 0x7fcd744f6610>
    >>>
    '''

    def __init__(self, finstance=None, fclass=None, doc=None):
        '''Instantiate the descriptor with the given parameters.

        If finstance is set, it must be a method implementing instance
        access. If fclass is set, it must be a method implementing class
        access similar to a classmethod. If doc is set, it will be used
        for the __doc__ attribute.  Otherwise, the __doc__ attribute
        from the instance or class method will be used, in that order.
        '''
        self.finstance = finstance
        self.fclass = fclass
        if doc is not None:
            self.__doc__ = doc
        elif finstance is not None:
            self.__doc__ = finstance.__doc__
        elif fclass is not None:
            self.__doc__ = fclass.__doc__

    def __get__(self, instance, owner):
        '''Descriptor getter method.

        See Python descriptor documentation.'''
        if instance is None:
            if self.fclass is None:
                if self.finstance is None:
                    raise AttributeError('no instance or class method is set')
                return MethodType(self.finstance, instance)
            return MethodType(self.fclass, owner)
        if self.finstance is None:
            if self.fclass is None:
                raise AttributeError('no instance or class method is set')
            return MethodType(self.fclass, owner)
        return MethodType(self.finstance, instance)

    def instancemethod(self, finstance):
        '''Descriptor to set the instance method.'''
        self.finstance = finstance
        return self

    def classmethod(self, fclass):
        '''Descriptor to set the class method.'''
        self.fclass = fclass
        return self

# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met: 
# 
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution. 
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
# 
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# 
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# pylint: disable=W0142,W0403
#}}}

'''VOLTTRON platform™ messaging utilities.'''

from string import Formatter


__all__ = ['normtopic', 'Topic']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2013, Battelle Memorial Institute'
__license__ = 'FreeBSD'


def normtopic(topic):
    '''Normalize topic, removing extra slashes and dots.'''
    if not topic:
        return topic
    comps = []
    for comp in topic.split('/'):
        if comp in ('', '.'):
            continue
        if comp == '..':
            comps.pop()
        else:
            comps.append(comp)
    return (u'/' if isinstance(topic, unicode) else '/').join(comps)


class TopicFormatter(Formatter):
    '''Format topic strings allowing for optional fields.

    TopicFormatter.format() works similar to the standard str.format()
    built-in, except that format strings may contain double forward
    slashes (//) to indicate break points in the string where a valid
    string may be returned if no replaceable fields occur in the
    following component.  A format field may optionally be passed
    through unsubstituted by passing a value of None for that field.

    Normal formatter processing splits the format string into a stream
    of string platformrals and replacement fields.  The replacement fields
    are replaced by values passed in via the positional and keyword
    arguments and are converted and formatted according to the field
    format before being substituted in the token stream.  Finally, the
    stream is concatenated and returned.  The first replacement field
    missing a value in the provided arguments stops processing and an
    exception is raised.  The topic formatter follows the same behavior
    except that instead of raising an exception, the previous platformral is
    truncated at the final double slash (//), and all the processed
    components are concatenated and the result returned.

    See the Formatter documentation for the built-in string module for
    more information on formatters and the role of each method.
    '''
    def _vformat(self, format_string, args, kwargs, used_args, recursion_depth):
        if recursion_depth < 0:
            raise ValueError('maximum string recursion exceeded')
        result = []
        for platformral, name, format_spec, conversion in self.parse(format_string):
            if platformral:
                result.append(platformral)
            if name is None:
                continue
            try:
                obj, arg_used = self.get_field(name, args, kwargs)
            except (KeyError, AttributeError) as e:
                if platformral:
                    try:
                        platformral, _ = platformral.rsplit('//', 1)
                    except ValueError:
                        pass
                    else:
                        result[-1] = platformral
                        break
                raise e
            used_args.add(arg_used)
            if obj is None:
                obj = '{{{}{}{}{}{}}}'.format(name,
                        '!' if conversion else '', conversion or '',
                        ':' if format_spec else '', format_spec or '')
            else:
                obj = self.convert_field(obj, conversion)
                format_spec = self._vformat(format_spec, args, kwargs,
                                            used_args, recursion_depth - 1)
                obj = self.format_field(obj, format_spec)
            result.append(obj)
        return ''.join(result)

    def check_unused_args(self, used_args, args, kwargs):
        for name in kwargs:
            if name not in used_args:
                raise ValueError('unused keyword argument: {}'.format(name))


class Topic(unicode):
    def __init__(self, format_string):
        '''Perform minimal validation of names used in format fields.'''
        for _, name, _, _ in format_string._formatter_parser():
            if name is None:
                continue
            name, _ = name._formatter_field_name_split()
            if isinstance(name, (int, long)) or not name:
                raise ValueError('positional format fields are not supported;'
                                 ' use named format fields only')
            if name[:1].isdigit():
                raise ValueError('invalid format field name: {}'.format(name))
    def __call__(self, **kwargs):
        return self.__class__(normtopic(self.vformat(kwargs)))
    def _(self, **kwargs):
        return self.__class__(self.vformat(kwargs))
    def format(self, **kwargs):
        return self.vformat(kwargs)
    def vformat(self, kwargs):
        formatter = TopicFormatter()
        return formatter.vformat(self, (), kwargs)
    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               super(Topic, self).__repr__())


class Header(str):
    pass


# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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
#}}}

'''VOLTTRON platform™ abstract agent for to drive VOLTTRON Nation apps.'''


from abc import ABCMeta, abstractmethod
from collections import defaultdict, OrderedDict
from datetime import datetime
import logging
import re

from . import utils


__all__ = ['AbstractDrivenAgent', 'ConversionMapper', 'Results']

__author__ = 'Craig Allwardt <craig.allwardt@pnnl.gov>'
__copyright__ = 'Copyright (c) 2014, Battelle Memorial Institute'
__license__ = 'FreeBSD'


class AbstractDrivenAgent(object):
    __metaclass__ = ABCMeta

    def __init__(self, out=None, **kwargs):
        """
        When applications extend this base class, they need to make
        use of any kwargs that were setup in config_param
        """
        super(AbstractDrivenAgent, self).__init__(**kwargs)
        self.out = out
        self.data = {}

    @classmethod
    @abstractmethod
    def output_format(cls, input_object):
        """
        The output object takes the resulting input object as a argument
        so that it may give correct topics to it's outputs if needed.

        output schema description
            {TableName1: {name1:OutputDescriptor1, name2:OutputDescriptor2,...},....}

            eg: {'OAT': {'Timestamp':OutputDescriptor('timestamp', 'foo/bar/timestamp'),'OAT':OutputDescriptor('OutdoorAirTemperature', 'foo/bar/oat')},
                'Sensor': {'SomeValue':OutputDescriptor('integer', 'some_output/value'),
                'SomeOtherValue':OutputDescriptor('boolean', 'some_output/value),
                'SomeString':OutputDescriptor('string', 'some_output/string)}}

        Should always call the parent class output_format and update the dictionary returned from
        the parent.

        result = super().output_format(input_object)
        my_output = {...}
        result.update(my_output)
        return result
        """
        return {}

    @abstractmethod
    def run(self, time, inputs):
        '''Do work for each batch of timestamped inputs
           time- current time
           inputs - dict of point name -> value

           Must return a results object.'''
        pass

    def shutdown(self):
        '''Override this to add shutdown routines.'''
        return Results()


class Results(object):
    def __init__(self, terminate=False):
        self.commands = OrderedDict()
        self.devices = OrderedDict()
        self.log_messages = []
        self._terminate = terminate
        self.table_output = defaultdict(list)

    def command(self, point, value, device=None):
        if device is None:
            self.commands[point] = value
        else:
            if device not in self.devices.keys():
                self.devices[device] = OrderedDict()
            self.devices[device][point] = value
        if self.devices is None:
            self.commands[point]=value
        else:
            if  device not in self.devices.keys():
                self.devices[device] = OrderedDict()
            self.devices[device][point]=value

    def log(self, message, level=logging.DEBUG):
        self.log_messages.append((level, message))

    def terminate(self, terminate):
        self._terminate = bool(terminate)

    def insert_table_row(self, table, row):
        self.table_output[table].append(row)


class ConversionMapper(object):

    def __init__(self, **kwargs):
        self.initialized = False
        utils.setup_logging()
        self._log = logging.getLogger(__name__)
        self.conversion_map = {}

    def setup_conversion_map(self, conversion_map_config, field_names):
        #time_format = conversion_map_config.pop(TIME_STAMP_COLUMN)
        re_exp_list = conversion_map_config.keys()
        re_exp_list.sort(cmp=lambda x, y: cmp(len(x), len(y)))
        re_exp_list.reverse()
        re_list = [re.compile(x) for x in re_exp_list]

        def default_handler():
            return lambda x:x
        self.conversion_map = defaultdict(default_handler)
        def handle_time(item):
            return datetime.strptime(item, time_format)
        #self.conversion_map[TIME_STAMP_COLUMN] = handle_time

        def handle_bool(item):
            item_lower = item.lower()
            if (item_lower == 'true' or
                item_lower == 't' or
                item_lower == '1'):
                return True
            return False
        type_map = {'int':int,
                    'float':float,
                    'bool':handle_bool}

        for name in field_names:
            for field_re in re_list:
                if field_re.match(name):
                    pattern = field_re.pattern
                    self._log.debug('Pattern {pattern} used to process {name}.'
                                    .format(pattern=pattern, name=name))
                    type_string = conversion_map_config[pattern]
                    self.conversion_map[name] = type_map[type_string]
                    break
                #else:
                #    if name != TIME_STAMP_COLUMN:
                #        self.log_message(logging.ERROR, 'FILE CONTROLLER', 'No matching map for column {name}. Will return raw string.'.format(name=name))
        self.initialized = True

    def process_row(self, row_dict):
        null_values = {'NAN', 'NA', '#NA', 'NULL', 'NONE',
                       'nan', 'na', '#na', 'null', 'none',
                       '', None}
        return dict((c,self.conversion_map[c](v)) if v not in null_values else (c,None) for c,v in row_dict.iteritems())

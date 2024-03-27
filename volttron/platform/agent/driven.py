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
__license__ = 'Apache 2.0'


class AbstractDrivenAgent(object, metaclass=ABCMeta):
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


class Results:
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
            if device not in self.devices:
                self.devices[device] = OrderedDict()
            self.devices[device][point] = value
        if self.devices is None:
            self.commands[point]=value
        else:
            if  device not in self.devices:
                self.devices[device] = OrderedDict()
            self.devices[device][point]=value

    def log(self, message, level=logging.DEBUG):
        self.log_messages.append((level, message))

    def terminate(self, terminate):
        self._terminate = bool(terminate)

    def insert_table_row(self, table, row):
        self.table_output[table].append(row)


class ConversionMapper:

    def __init__(self, **kwargs):
        self.initialized = False
        utils.setup_logging()
        self._log = logging.getLogger(__name__)
        self.conversion_map = {}

    def setup_conversion_map(self, conversion_map_config, field_names):
        #time_format = conversion_map_config.pop(TIME_STAMP_COLUMN)
        re_exp_list = list(conversion_map_config.keys())
        re_exp_list.sort(key=lambda x: len(x), reverse=True)
        re_exp_list.reverse()
        re_list = [re.compile(x) for x in re_exp_list]

        def default_handler():
            return lambda x:x
        self.conversion_map = defaultdict(default_handler)
        # def handle_time(item):
        #     return datetime.strptime(item, time_format)
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
        return dict((c,self.conversion_map[c](v)) if v not in null_values else (c,None) for c,v in row_dict.items())

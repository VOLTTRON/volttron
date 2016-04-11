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

# }}}
import sys
import logging
from datetime import timedelta as td, datetime as dt
from copy import deepcopy
from dateutil import parser
from sympy import symbols
from sympy.parsing.sympy_parser import parse_expr
import abc
from collections import deque

from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.agent.utils import jsonapi, setup_logging
from volttron.platform.vip.agent import Agent, Core
from ilc.ilc_matrices import (extract_criteria, calc_column_sums,
                              normalize_matrix, validate_input,
                              build_score, input_matrix)
from volttron.platform.jsonrpc import RemoteError
import gevent

__version__ = '2.0.0'

MATRIX_ROWSTRING = '%20s\t%12.2f%12.2f%12.2f%12.2f%12.2f'
CRITERIA_LABELSTRING = '\t\t\t%12s%12s%12s%12s%12s'
DATE_FORMAT = '%m-%d-%y %H:%M:%S'
setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug,
                    format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt='%m-%d-%y %H:%M:%S')
mappers = {}
criterion_registry = {}


def register_criterion(name):
    def decorator(klass):
        criterion_registry[name] = klass
        return klass
    return decorator


class BaseCriterion(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, minimum=None, maximum=None):
        self.min_func = (lambda x: x) if minimum is None else (lambda x: max(x, minimum))
        self.max_func = (lambda x: x) if maximum is None else (lambda x: min(x, maximum))
        self.minimum = minimum
        self.maximum = maximum

    def evaluate_bounds(self, value):
        value = self.min_func(value)
        value = self.max_func(value)
        return value

    def evaluate_criterion(self):
        value = self.evaluate()
        value = self.evaluate_bounds(value)
        return value

    @abc.abstractmethod
    def evaluate(self):
        pass

    def ingest_data(self, time_stamp, data):
        pass


@register_criterion('status')
class StatusCriterion(BaseCriterion):
    def __init__(self, on_value=None, off_value=0.0,
                 point_name=None, **kwargs):
        super(StatusCriterion, self).__init__(**kwargs)
        if on_value is None or point_name is None:
            raise ValueError('Missing parameter')
        self.on_value = on_value
        self.off_value = off_value
        self.point_name = point_name
        self.current_status = False

    def evaluate(self):
        if self.current_status:
            val = self.on_value
        else:
            val = self.off_value
        return val

    def ingest_data(self, time_stamp, data):
        self.current_status = bool(data[self.point_name])


@register_criterion('constant')
class ConstantCriterion(BaseCriterion):
    def __init__(self, value=None, off_value=0.0,
                 point_name=None, **kwargs):
        super(ConstantCriterion, self).__init__(**kwargs)
        if value is None:
            raise ValueError('Missing parameter')
        self.value = value

    def evaluate(self):
        return self.value


@register_criterion('formula')
class FormulaCriterion(BaseCriterion):
    def __init__(self, operation=None, operation_args=None, **kwargs):
        super(FormulaCriterion, self).__init__(**kwargs)
        if operation is None or operation_args is None:
            raise ValueError('Missing parameter')
        self.operation_args = operation_args
        self.points = symbols(operation_args)
        self.expr = parse_expr(operation)

    def evaluate(self):
        if self.pt_list:
            val = self.expr.subs(self.pt_list)
        else:
            val = self.minimum
        return val

    def ingest_data(self, time_stamp, data):
        pt_list = []
        for item in self.operation_args:
            pt_list.append((item, data[item]))
        self.pt_list = pt_list


@register_criterion('mapper')
class MapperCriterion(BaseCriterion):
    def __init__(self, dict_name=None, map_key=None, **kwargs):
        super(MapperCriterion, self).__init__(**kwargs)
        if dict_name is None or map_key is None:
            raise ValueError('Missing parameter')
        self.value = mappers[dict_name][map_key]

    def evaluate(self):
        return self.value


@register_criterion('history')
class HistoryCriterion(BaseCriterion):
    def __init__(self, comparison_type=None,
                 point_name=None, previous_time=None, **kwargs):
        super(HistoryCriterion, self).__init__(**kwargs)
        if (comparison_type is None or point_name is None or
                previous_time is None):
            raise ValueError('Missing parameter')
        self.history = deque()
        self.comparison_type = comparison_type
        self.point_name = point_name
        self.previous_time_delta = td(minutes=previous_time)

        self.current_value = None
        self.history_time = None

    def linear_interpolation(self, date1, value1, date2, value2, target_date):
        end_delta_t = (date2-date1).total_seconds()
        target_delta_t = (target_date-date1).total_seconds()
        return (value2-value1)*(target_delta_t / end_delta_t) + value1

    def evaluate(self):
        if self.current_value is None:
            return self.minimum

        pre_timestamp, pre_value = self.history.pop()

        if pre_timestamp > self.history_time:
            self.history.append((pre_timestamp, pre_value))
            return self.minimum

        post_timestamp, post_value = self.history.pop()

        while post_timestamp < self.history_time:
            pre_value, pre_timestamp = post_value, post_timestamp
            post_timestamp, post_value = self.history.pop()

        self.history.append((post_timestamp, post_value))
        prev_value = self.linear_interpolation(pre_timestamp, pre_value,
                                               post_timestamp, post_value,
                                               self.history_time)
        if self.comparison_type == 'direct':
            val = abs(prev_value - self.current_value)
        elif self.comparison_type == 'inverse':
            val = 1/abs(prev_value - self.current_value)
        return val

    def ingest_data(self, time_stamp, data):
        self.history_time = time_stamp - self.previous_time_delta
        self.current_value = data[self.point_name]
        self.history.appendleft((time_stamp, self.current_value))
        
        
class CurtailmentSetting(object):
    def __init__(self, point = None, value = None, load = None, offset=None):
        if None in (point, value, load):
            raise ValueError('Missing parameter')
        self.point = point
        self.load = load
        self.value = value
        self.offset = offset
        
    def ingest_data(self, data):
        if self.offset is not None:
            base = data[self.point]
            self.value = base + self.offset
            _log.debug("Setting offest value for curtail: Base value: {}, Offset: {}, New value: {}".format(base, self.offset, self.value))
            
    def get_curtailment_dict(self):
        return {"point": self.point,
                "value": self.value,
                "load": self.load}

class ConditionalCurtailment(object):
    def __init__(self, condition = None, conditional_args = None, **kwargs):
        if None in (condition, conditional_args):
            raise ValueError('Missing parameter')
        self.conditional_args = conditional_args
        self.points = symbols(conditional_args)
        self.expr = parse_expr(condition)
        self.condition = condition
        
        self.curtailment = CurtailmentSetting(**kwargs)

    def check_condition(self):
        if self.pt_list:
            val = self.expr.subs(self.pt_list)
            _log.debug("{} evaluated to {}".format(self.condition, val))
        else:
            val = False
        return val

    def ingest_data(self, data):
        pt_list = []
        for item in self.conditional_args:
            pt_list.append((item, data[item]))
        self.pt_list = pt_list
        self.curtailment.ingest_data(data)
        
    def get_curtailment(self):
        return self.curtailment.get_curtailment_dict()
    
#     def __str__(self):
#         
    
class CurtailmentManager(object):
    def __init__(self, conditional_curtailment_settings = [], **kwargs):
        
        self.default_curtailment = CurtailmentSetting(**kwargs)
        
        self.conditional_curtailments = []
        for settings in conditional_curtailment_settings:
            conditional_curtailment = ConditionalCurtailment(**settings)
            self.conditional_curtailments.append(conditional_curtailment)
            
    def ingest_data(self, data):
        for conditional_curtailment in self.conditional_curtailments:
            conditional_curtailment.ingest_data(data)
            
        self.default_curtailment.ingest_data(data)
            
    def get_curtailment(self):
        curtailment = self.default_curtailment.get_curtailment_dict()
        
        for conditional_curtailment in self.conditional_curtailments:
            if conditional_curtailment.check_condition():
                curtailment = conditional_curtailment.get_curtailment()
                break
            
        return curtailment

class Criteria(object):
    def __init__(self, criteria):
        self.currently_curtailed = False
        self.criteria = {}
        criteria = deepcopy(criteria)

        default_curtailment = criteria.pop('curtail')
        conditional_curtailment = criteria.pop('conditional_curtail', [])
        
        self.curtailment_manager = CurtailmentManager(conditional_curtailment_settings = conditional_curtailment,
                                                      **default_curtailment)

        self.curtail_count = 0

        for name, criterion in criteria.items():
            self.add(name, criterion)

    def add(self, name, criterion):
        operation_type = criterion.pop('operation_type')
        klass = criterion_registry[operation_type]
        self.criteria[name] = klass(**criterion)

    def evaluate(self):
        results = {}
        for name, criterion in self.criteria.items():
            result = criterion.evaluate_criterion()
            results[name] = result

        results['curtail_count'] = self.curtail_count
        return results

    def ingest_data(self, time_stamp, data):
        for criterion in self.criteria.values():
            criterion.ingest_data(time_stamp, data)
            
        self.curtailment_manager.ingest_data(data)

    def reset_curtail_count(self):
        self.curtail_count = 0.0

    def increment_curtail(self):
        self.currently_curtailed = False
        self.curtail_count += 1.0

    def get_curtailment(self):
        return self.curtailment_manager.get_curtailment()

    def reset_currently_curtailed(self):
        self.currently_curtailed = True


class Device(object):
    def __init__(self, device_config):
        self.criteria = {}
        self.command_status = {}

        for command_point, criteria_config in device_config.items():
            criteria = Criteria(criteria_config)
            self.criteria[command_point] = criteria
            self.command_status[command_point] = False

    def ingest_data(self, time_stamp, data):
        for criteria in self.criteria.values():
            criteria.ingest_data(time_stamp, data)

        for command in self.command_status:
            self.command_status[command] = bool(data[command])

    def reset_curtail_count(self):
        for criteria in self.criteria.values():
            criteria.reset_curtail_count()

    def reset_currently_curtailed(self):
        for criteria in self.criteria.values():
            criteria.reset_currently_curtailed()

    def increment_curtail(self, command):
        self.criteria[command].increment_curtail()

    def evaluate(self, command):
        return self.criteria[command].evaluate()

    def get_curtailment(self, command):
        return self.criteria[command].get_curtailment()

    def get_on_commands(self):
        return [command for command, state in self.command_status.iteritems() if state]


class DeviceCluster(object):
    def __init__(self, priority, crit_labels, row_average, cluster_config):
        self.devices = {}
        self.priority = priority
        self.crit_labels = crit_labels
        self.row_average = row_average

        for device_name, device_config in cluster_config.iteritems():
            self.devices[device_name] = Device(device_config)

    def get_all_device_evaluations(self):
        results = {}
        for name, device in self.devices.iteritems():
            for command in device.get_on_commands():
                evaluations = device.evaluate(command)
                results[name, command] = evaluations
        return results


class Clusters(object):
    def __init__(self):
        self.clusters = []
        self.devices = {}

    def add_device_cluster(self, cluster):
        self.clusters.append(cluster)
        self.devices.update(cluster.devices)

    def get_device_name_list(self):
        return self.devices.keys()

    def get_device(self, device_name):
        return self.devices[device_name]

    def reset_curtail_count(self):
        for device in self.devices.itervalues():
            device.reset_curtail_count()

    def reset_currently_curtailed(self):
        for device in self.devices.itervalues():
            device.reset_currently_curtailed()

    def get_score_order(self):
        all_scored_devices = []
        for cluster in self.clusters:
            device_evaluations = cluster.get_all_device_evaluations()

            _log.debug('Device Evaluations: ' + str(device_evaluations))

            if not device_evaluations:
                continue

            input_arr = input_matrix(device_evaluations, cluster.crit_labels)
            _log.debug('Input Array: ' + str(input_arr))
            scored_devices = build_score(input_arr, cluster.row_average, cluster.priority)
            all_scored_devices.extend(scored_devices)

        all_scored_devices.sort(reverse=True)
        _log.debug('Scored Devices: ' + str(all_scored_devices))
        results = [x[1] for x in all_scored_devices]

        return results


def ilc_agent(config_path, **kwargs):
    '''Intelligent Load Curtailment (ILC) Application using

    Analytical Hierarchical Process (AHP).
    '''
    config = utils.load_config(config_path)
    location = {}
    location['campus'] = config.get('campus')
    location['building'] = config.get('building')
    cluster_configs = config['clusters']
    agent_id = config.get('agent_id')

    global mappers

    try:
        mappers = config['mappers']
    except KeyError:
        mappers = {}

    clusters = Clusters()

    for cluster_config in cluster_configs:
        excel_file_name = cluster_config['critieria_file_path']
        cluster_config_file_name = cluster_config['device_file_path']
        cluster_priority = cluster_config['cluster_priority']

        crit_labels, criteria_arr = extract_criteria(excel_file_name, 'CriteriaMatrix')
        col_sums = calc_column_sums(criteria_arr)
        _, row_average = normalize_matrix(criteria_arr, col_sums)

        if not (validate_input(criteria_arr, col_sums, 
                               crit_labels, CRITERIA_LABELSTRING,
                               MATRIX_ROWSTRING)):
            _log.info('Inconsistent criteria matrix. Check configuration '
                      'in ' + excel_file_name)
            sys.exit()
        cluster_config = utils.load_config(cluster_config_file_name)
        device_cluster = DeviceCluster(cluster_priority, crit_labels, row_average, cluster_config)

        _log.debug('Crit Labels: ' + str(crit_labels))
        clusters.add_device_cluster(device_cluster)

    base_device_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''),
                                             building=config.get('building', ''),
                                             unit=None,
                                             path='',
                                             point=None)

    base_rpc_path = topics.RPC_DEVICE_PATH(campus=config.get('campus', ''),
                                                building=config.get('building', ''),
                                                unit=None,
                                                path='',
                                                point=None)

    device_topic_list = []
    device_topic_map = {}
    all_devices = clusters.get_device_name_list()

    for device_name in all_devices:
        device_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''),
                                            building=config.get('building', ''),
                                            unit=device_name,
                                            path='',
                                            point='all')
        device_topic_list.append(device_topic)
        device_topic_map[device_topic] = device_name

    power_token = config['power_meter']
    power_meter = power_token['device']
    power_pt = power_token['point']
    power_meter_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''),
                                             building=config.get('building', ''),
                                             unit=power_meter,
                                             path='',
                                             point='all')

    kill_device_topic = None
    kill_token = config.get('kill_switch')
    if kill_token is not None:
        kill_device = kill_token['device']
        kill_pt = kill_token['point']
        kill_device_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''),
                                                 building=config.get('building', ''),
                                                 unit=kill_device,
                                                 path='',
                                                 point='all')

    demand_limit = float(config['demand_limit'])
    curtail_time = td(minutes=config.get('curtailment_time', 15.0))
    average_building_power_window = td(minutes=config.get('average_building_power_window', 5.0))
    curtail_confirm = td(minutes=config.get('curtailment_confirm', 5.0))
    curtail_break = td(minutes=config.get('curtailment_break', 5.0))
    actuator_schedule_buffer = td(minutes=config.get('actuator_schedule_buffer', 5.0))
    reset_curtail_count_time = td(hours=config.get('reset_curtail_count_time', 6.0))
    longest_possible_curtail = len(clusters.devices) * curtail_time

    class AHP(Agent):
        def __init__(self, **kwargs):
            super(AHP, self).__init__(**kwargs)
            self.running_ahp = False
            self.row_average = None
            self.next_curtail_confirm = None
            self.curtail_end = None
            self.break_end = None
            self.reset_curtail_count_time = None
            self.kill_signal_recieved = False
            self.scheduled_devices = set()
            self.devices_curtailed = set()
            self.bldg_power = []

        @Core.receiver('onstart')
        def starting_base(self, sender, **kwargs):
            '''startup method:
             - Extract Criteria Matrix from excel file.
             - Setup subscriptions to curtailable devices.
             - Setup subscription to building power meter.
            '''
            for device_topic in device_topic_list:
                _log.debug('Subscribing to '+device_topic)
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=device_topic,
                                          callback=self.new_data)
            _log.debug('Subscribing to '+power_meter_topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=power_meter_topic,
                                      callback=self.load_message_handler)

            if kill_device_topic is not None:
                _log.debug('Subscribing to '+kill_device_topic)
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=kill_device_topic,
                                          callback=self.handle_agent_kill)

        def handle_agent_kill(self, peer, sender, bus, topic, headers, message):
            '''
            Locally implemented override for ILC application.

            When an override is detected the ILC application will return
            operations for all units to normal.
            '''
            data = message[0]
            _log.info('Checking kill signal')
            kill_signal = bool(data[kill_pt])

            if kill_signal:
                _log.info('Kill signal received, shutting down')
                self.kill_signal_recieved = False
                gevent.sleep(8)
                self.end_curtail()
                sys.exit()

        def new_data(self, peer, sender, bus, topic, headers, message):
            '''Call back method for curtailable device data subscription.'''
            if self.kill_signal_recieved:
                return

            _log.info('Data Received for {}'.format(topic))

            # topic of form:  devices/campus/building/device
            device_name = device_topic_map[topic]

            data = message[0]
            now = parser.parse(headers['Date'])

            clusters.get_device(device_name).ingest_data(now, data)

        def load_message_handler(self, peer, sender, bus, topic, headers, message):
            '''Call back method for building power meter. Calculates the average
            building demand over a configurable time and manages the curtailment
            time and curtailment break times.
            '''
            if self.kill_signal_recieved:
                return

            _log.debug('Reading building power data.')
            current_power = float(message[0][power_pt])

            if current_power < 0:
                current_power = 0.0

            now = parser.parse(headers['Date'])
            self.bldg_power.append((now, current_power))
            if self.bldg_power[-1][0] - self.bldg_power[0][0] > average_building_power_window:
                self.bldg_power.pop(0)
            average_power = sum(power[1] for power in self.bldg_power)/len(self.bldg_power)

            _log.debug('Reported time: '+str(now))
            _log.info('Current load: {}'.format(average_power))

            if self.reset_curtail_count_time is not None:
                if self.reset_curtail_count_time <= now:
                    _log.debug('Resetting curtail count')
                    clusters.reset_curtail_count()

            if self.running_ahp:

                if now >= self.curtail_end:
                    self.end_curtail()

                elif now >= self.next_curtail_confirm:
                    self.curtail_confirm(average_power, now)
                return

            elif self.break_end is not None and now < self.break_end:
                _log.debug('Skipping load check, still on curtailment break.')
                return

            self.check_load(average_power, now)

        def check_load(self, bldg_power, now):
            '''Check whole building power and if the value is above the

            the demand limit (demand_limit) then initiate the ILC (AHP)
            sequence.
            '''
            _log.debug('Checking building load.')

            if bldg_power > demand_limit:
                _log.info('Current load ({load}) exceeds limit or {limit}.'.format(load=bldg_power, limit=demand_limit))

                score_order = clusters.get_score_order()
                if not score_order:
                    _log.info('All devices are off, nothing to curtail.')
                    return

                scored_devices = self.actuator_request(score_order)
                self.curtail(scored_devices, bldg_power, now)

        def curtail(self, scored_devices, bldg_power, now):
            '''Curtail loads by turning off device (or device components)'''
            need_curtailed = bldg_power - demand_limit
            est_curtailed = 0.0
            remaining_devices = scored_devices[:]

            for device in self.devices_curtailed:
                if device in remaining_devices:
                    remaining_devices.remove(device)

            if not self.running_ahp:
                _log.info('Starting AHP')
                self.running_ahp = True
                
            if not remaining_devices:
                _log.debug("Everything available has already been curtailed")
                return 

            self.curtail_end = now + curtail_time
            self.break_end = now + curtail_break + curtail_time
            self.reset_curtail_count_time = self.curtail_end + reset_curtail_count_time
            self.next_curtail_confirm = now + curtail_confirm

            _log.info('Curtialing load.')

            for item in remaining_devices:

                device_name, command = item

                curtail = clusters.get_device(device_name).get_curtailment(command)

                curtail_pt = curtail['point']
                curtail_val = curtail['value']
                curtail_load = curtail['load']

                curtailed_point = base_rpc_path(unit=device_name, point=curtail_pt)
                # TODO: catch errors.
                _log.debug('Setting '+curtailed_point+' to '+str(curtail_val))

                try:
                    if self.kill_signal_recieved:
                        break
                    result = self.vip.rpc.call('platform.actuator', 'set_point',
                                               agent_id, curtailed_point,
                                               curtail_val).get(timeout=4)
                except RemoteError as ex:
                    _log.warning("Failed to set {} to {}: {}".format(curtailed_point, curtail_val, str(ex)))
                    continue

                est_curtailed += curtail_load
                clusters.get_device(device_name).increment_curtail(command)
                self.devices_curtailed.add(item)

                if est_curtailed >= need_curtailed:
                    break

            return

        def curtail_confirm(self, cur_pwr, now):
            '''Check if load shed has been met.  If the demand goal is not

            met and there are additional devices to curtail then the ILC will shed
            additional load by curtailing more devices.
            '''
            if cur_pwr < demand_limit:
                _log.info('Curtail goal for building load met.')
            else:
                _log.info('Curtail goal for building load NOT met.')
                self.check_load(cur_pwr, now)

        def actuator_request(self, score_order):
            '''request access to devices.'''
            _now = dt.now()
            str_now = _now.strftime(DATE_FORMAT)
            _end = _now + longest_possible_curtail + actuator_schedule_buffer
            str_end = _end.strftime(DATE_FORMAT)
            ctrl_dev = []

            already_handled = dict((device, True) for device in self.scheduled_devices)

            for item in score_order:

                device, point = item

                _log.debug('Reserving device: ' + device)

                if device in already_handled:
                    if already_handled[device]:
                        _log.debug('Skipping reserve device (previously reserved): ' + device)
                        ctrl_dev.append(item)
                    continue

                curtailed_device = base_rpc_path(unit=device, point='')
                schedule_request = [[curtailed_device, str_now, str_end]]
                try:
                    if self.kill_signal_recieved:
                        break
                    result = self.vip.rpc.call(
                        'platform.actuator', 'request_new_schedule', agent_id,
                        device, 'HIGH', schedule_request).get(timeout=4)
                except RemoteError as ex:
                    _log.warning("Failed to schedule device {} (RemoteError): {}".format(device, str(ex)))
                    continue

                if result['result'] == 'FAILURE':
                    _log.warn('Failed to schedule device (unavailable) ' + device)
                    already_handled[device] = False
                else:
                    already_handled[device] = True
                    self.scheduled_devices.add(device)
                    ctrl_dev.append(item)

            return ctrl_dev

        def end_curtail(self):
            self.running_ahp = False
            self.reset_devices()
            self.release_devices()

        def reset_devices(self):
            _log.info('Resetting devices')
            for item in self.devices_curtailed:

                device_name, command = item
                curtail = clusters.get_device(device_name).get_curtailment(command)
                curtail_pt = curtail['point']
                curtailed_point = base_rpc_path(unit=device_name, point=curtail_pt)
                try:
                    result = self.vip.rpc.call('platform.actuator', 'revert_point',
                                               agent_id, curtailed_point).get(timeout=10)
                    _log.debug('Reverted point: {}'.format(curtailed_point))
                except RemoteError as ex:
                    _log.warning("Failed to revert point {} (RemoteError): {}".format(curtailed_point, str(ex)))
                    continue

            self.devices_curtailed = set()

        def release_devices(self):
            for device in self.scheduled_devices:
                result = self.vip.rpc.call(
                    'platform.actuator', 'request_cancel_schedule', agent_id,
                    device).get(timeout=10)

            self.scheduled_devices = set()

    return AHP(**kwargs)


def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(ilc_agent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

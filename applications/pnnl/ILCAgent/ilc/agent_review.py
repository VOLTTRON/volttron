import sys
import logging
from pandas import DataFrame as df
import numpy as np
from datetime import timedelta as td, datetime as dt
from copy import deepcopy
from dateutil import parser
# from _ast import comprehension
from sympy import symbols
from sympy.parsing.sympy_parser import parse_expr
import abc
from collections import deque

# from volttron.platform.agent import utils, matching, sched
# from volttron.platform.messaging import headers as headers_mod,
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.agent.utils import jsonapi, setup_logging
from volttron.platform.vip.agent import Agent, Core
from ilc.ilc_matrices import (extract_criteria, calc_column_sums,
                              normalize_matrix, validate_input,
                              build_score, input_matrix)

__version__ = "1.0.0"

MATRIX_ROWSTRING = "%20s\t%12.2f%12.2f%12.2f%12.2f%12.2f"
CRITERIA_LABELSTRING = "\t\t\t%12s%12s%12s%12s%12s"
DATE_FORMAT = '%m-%d-%y %H:%M:%S'
TESTING = True
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
        self.min_func = lambda x: x if minimum is None else lambda x: min(x, minimum)
        self.max_func = lambda x: x if maximum is None else lambda x: max(x, maximum)
        self.minimum = minimum
        self.maximum = maximum

    def evaluate_bounds(self, value):
        value = self.min_func(value)
        value = self.max_func(value)
        return value

    def evaluate_criterion(self, data):
        value = self.evaluate(data)
        value = self.evaluate_bounds(value)
        return value

    @abc.abstractmethod
    def evaluate(self):
        pass

    def ingest_data(self, time_stamp, data):
        pass


@register_criterion("status")
class StatusCriterion(BaseCriterion):
    def __init__(self, on_value=None, off_value=0.0,
                 point_name=None, **kwargs):
        super(StatusCriterion, self).__init__(**kwargs)
        if on_value is None or point_name is None:
            raise ValueError("Missing parameter")
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


@register_criterion("constant")
class ConstantCriterion(BaseCriterion):
    def __init__(self, value=None, off_value=0.0,
                 point_name=None, **kwargs):
        super(ConstantCriterion, self).__init__(**kwargs)
        if value is None:
            raise ValueError("Missing parameter")
        self.value = value

    def evaluate(self):
        return self.value


@register_criterion("formula")
class FormulaCriterion(BaseCriterion):
    def __init__(self, operation=None, operation_args=None, **kwargs):
        super(FormulaCriterion, self).__init__(**kwargs)
        if operation is None or operation_args is None:
            raise ValueError("Missing parameter")
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


@register_criterion("mapper")
class MapperCriterion(BaseCriterion):
    def __init__(self, dict_name=None, map_key=None, **kwargs):
        super(MapperCriterion, self).__init__(**kwargs)
        if dict_name is None or map_key is None:
            raise ValueError("Missing parameter")
        self.value = mappers[dict_name][map_key]

    def evaluate(self):
        return self.value


@register_criterion("history")
class HistoryCriterion(BaseCriterion):
    def __init__(self, comparison_type=None,
                 point_name=None, previous_time=None, **kwargs):
        super(HistoryCriterion, self).__init__(**kwargs)
        if (comparison_type is None or point_name is None or
                previous_time is None):
            raise ValueError("Missing parameter")
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

        post_timestamp, post_value  = self.history.pop()

        while post_timestamp < self.history_time:
            pre_value, pre_timestamp = post_value, post_timestamp
            post_timestamp, post_value  = self.history.pop()

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


class Criteria(object):
    def __init__(self, criteria):
        self.criteria = {}
        criteria = deepcopy(criteria)

        self.curtailment = criteria.pop("curtail")

        # Verify all curtailment parameters.
        for key in ('point', 'value', 'load'):
            if key not in self.curtailment:
                raise Exception("Missing {key} parameter from curtailment settings.".format(key=key))

        self.curtail_count = 0

        for name, criterion in criteria.items():
            self.add(name, criterion)

    def add(self, name, criterion):
        operation_type = criterion.pop("operation_type")
        klass = criterion_registry[operation_type]
        self.criteria[name] = klass(**criterion)

    def evaluate(self):
        results = {}
        for name, criterion in self.criteria.items():
            result = criterion.evaluate()
            results[name] = result

        results["curtail_count"] = self.curtail_count
        return results

    def ingest_data(self, time_stamp, data):
        for criterion in self.criteria.values():
            criterion.ingest_data(time_stamp, data)

    def reset_curtail(self):
        self.curtail_count = 0.0

    def increment_curtail(self):
        self.curtail_count += 1.0

    def get_curtailment(self):
        return self.curtailment.copy()


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

    def reset_curtail(self):
        for criteria in self.criteria.values():
            criteria.reset_curtail()

    def increment_curtail(self, command):
        self.criteria[command].increment_curtail()

    def evaluate(self, command):
        return self.criteria[command].evaluate()

    def get_curtailment(self, command):
        return self.criteria[command].get_curtailment()

    def get_off_commands(self):
        return [command for command, state in self.command_status.iteritems() if not state]

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

    def get_off_device_set(self):
        results = set()
        for name, device in self.devices.iteritems():
            results.update(((name, command) for command in device.get_off_commands()))

        return results

    def get_on_device_set(self):
        results = set()
        for name, device in self.devices.iteritems():
            results.update(((name, command) for command in device.get_on_commands()))

        return results

    def get_score_order(self):
        all_scored_devices = []
        for cluster in self.clusters:
            device_evaluations = cluster.get_all_device_evaluations()

            if not device_evaluations:
                continue

            input_arr = input_matrix(device_evaluations, cluster.crit_labels)
            scored_devices = build_score(input_arr, cluster.row_average, cluster.priority)
            all_scored_devices.extend(scored_devices)

        all_scored_devices.sort()
        results = [x[1] for x in all_scored_devices]

        return results


def ahp(config_path, **kwargs):
    '''Intelligent Load Curtailment Algorithm'

    using Analytical Hierarchical Process.
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
        excel_file_name = cluster_config["critieria_file_path"]
        cluster_config_file_name = cluster_config["device_file_path"]
        cluster_priority = cluster_config["cluster_priority"]

        crit_labels, criteria_arr = extract_criteria(excel_file_name, "CriteriaMatrix")
        col_sums = calc_column_sums(criteria_arr)
        _, row_average = normalize_matrix(criteria_arr, col_sums)

        if not (validate_input(criteria_arr, col_sums, False,
                               crit_labels, CRITERIA_LABELSTRING,
                               MATRIX_ROWSTRING)):
            _log.info('Inconsistent criteria matrix. Check configuration '
                      'in ' + excel_file_name)
            sys.exit()
        cluster_config = utils.load_config(cluster_config_file_name)
        device_cluster = DeviceCluster(cluster_priority, crit_labels, row_average, cluster_config)
        clusters.add_device_cluster(device_cluster)

    base_device_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''),
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

    demand_limit = float(config["demand_limit"])
    curtail_time = td(minutes=config.get("curtailment_time", 15.0))
    curtail_confirm = td(minutes=config.get("curtailment_confirm", 5.0))
    curtail_break = td(minutes=config.get("curtailment_break", 5.0))
    actuator_schedule_buffer = td(minutes=config.get("actuator_schedule_buffer", 5.0))

    class AHP(Agent):
        def __init__(self, **kwargs):
            super(AHP, self).__init__(**kwargs)
            self.running_ahp = False
            self.crit_labels = None
            self.row_average = None
            self.remaining_devices = []
            self.saved_off_device_set = set()
            self.next_curtail_confirm = None
            self.curtail_end = None
            self.break_end = None
            self.scheduled_devices = set()
            self.devices_curtailed = set()

        @Core.receiver("onstart")
        def starting_base(self, sender, **kwargs):
            '''startup method:
             - Extract Criteria Matrix from excel file.
             - Setup subscriptions to device and building power meter.
            '''
            for device_topic in device_topic_list:
                _log.debug("Subscribing to "+device_topic)
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=device_topic,
                                          callback=self.new_data)
            _log.debug("Subscribing to "+power_meter_topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=power_meter_topic,
                                      callback=self.load_message_handler)

        def new_data(self, peer, sender, bus, topic, headers, message):
            '''Generate static configuration inputs for

            priority calculation.
            '''
            _log.info('Data Received')

            # topic of form:  devices/campus/building/device
            device_name = device_topic_map[topic]

            data = message[0]
            now = parser.parse(headers['Date'])
            
            clusters.get_device(device_name).ingest_data(now, data)

        def load_message_handler(self, peer, sender, bus, topic, headers, message):
            _log.debug('Reading building power data.')
            bldg_power = float(message[0][power_pt])

            
            now = parser.parse(headers['Date'])

            if self.running_ahp:

                if now >= self.curtail_end:
                    self.end_curtail()

                elif now >= self.next_curtail_confirm:
                    self.curtail_confirm(bldg_power)
                return

            elif self.break_end is not None and now < self.break_end:
                return

            self.check_load(bldg_power)

        def check_load(self, bldg_power):
            '''Check whole building power and if the value is above the

            the demand limit (demand_limit) then initiate the AHP sequence.
            '''
            _log.debug('Checking building load.')

            if bldg_power > demand_limit:
                _log.info('Current load ({load}) exceeds limit or {limit}.'.format(load=bldg_power, limit=demand_limit))

                self.saved_off_device_set = clusters.get_off_device_set()

                score_order = clusters.get_score_order()
                if not score_order:
                    _log.info('All devices are off, nothing to curtail.')
                    return
                
                print score_order

                scored_devices = self.actuator_request(score_order)
                self.remaining_devices = self.curtail(scored_devices, bldg_power)

        def curtail(self, scored_devices, bldg_power):
            '''Curtail loads by turning off device (or device components'''
            need_curtailed = bldg_power - demand_limit
            est_curtailed = 0.0
            remaining_devices = scored_devices[:]

            # Don't restart timer if ahp is running.
            # curtail_confirm updates the next confirm time after this.
            now = dt.now()

            if not self.running_ahp:
                _log.info('Starting AHP')
                self.curtail_end = now + curtail_time
                self.break_end = now + curtail_break
                self.running_ahp = True

            self.next_curtail_confirm = now + curtail_confirm

            _log.info('Curtialing load.')

            for item in scored_devices:

                device_name, command = item

                curtail = clusters.get_device(device_name).get_curtailment(command)

                curtail_pt = curtail['point']
                curtail_val = curtail['value']
                curtail_load = curtail['load']

                curtailed_point = base_device_topic(unit=device_name, point=curtail_pt)
                # TODO: catch errors.
                result = self.vip.rpc.call('platform.actuator', 'set_point',
                                           agent_id, curtailed_point,
                                           curtail_val).get(timeout=10)
                est_curtailed += curtail_load
                clusters.get_device(device_name).increment_curtail(command)
                self.devices_curtailed.add(item)

                if est_curtailed >= need_curtailed:
                    break

            for device in self.devices_curtailed:
                remaining_devices.remove(device)

            return remaining_devices

        def curtail_confirm(self, cur_pwr):
            '''Check if load shed goal is met.'''
            if cur_pwr < demand_limit:
                _log.info('Curtail goal for building load met.')
            else:
                _log.info('Curtail goal for building load NOT met.')
                on_device_set = clusters.get_on_device_set()
                new_on_device_set = self.saved_off_device_set.union(on_device_set)

                if not new_on_device_set:
                    if self.remaining_devices:
                        self.remaining_devices = self.curtail(self.remaining_devices, cur_pwr)
                    else:
                        _log.info('Did not meet load curtailment goal but there '
                                  'are no further available loads to remove.')
                else:
                    self.check_load(cur_pwr)

        def actuator_request(self, score_order):
            '''request access to devices.'''
            _now = dt.now()
            str_now = _now.strftime(DATE_FORMAT)
            _end = _now + curtail_time + actuator_schedule_buffer
            str_end = _end.strftime(DATE_FORMAT)
            ctrl_dev = []
            already_handled = {}
            for item in score_order:

                device, point = item
                
                _log.debug("Reserving device: " + device)

                if device in already_handled or device in self.scheduled_devices:
                    if already_handled[device]:
                        _log.debug("Skipping reserve device (previously reserved): " + device)
                        ctrl_dev.append(item)
                    continue

                curtailed_device = base_device_topic(unit=device, point='')
                schedule_request = [[curtailed_device, str_now, str_end]]
                result = self.vip.rpc.call(
                    'platform.actuator', 'request_new_schedule', agent_id,
                    device, 'HIGH', schedule_request).get(timeout=10)
                if result['result'] == 'FAILURE':
                    _log.warn("Failed to schedule device: " + device)
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
            _log.info("Resetting devices")
            for item in self.devices_curtailed:

                device_name, command = item
                curtail = clusters.get_device(device_name).get_curtailment(command)
                curtail_pt = curtail['point']
                curtail_val = None
                curtailed_point = base_device_topic(unit=device_name, point=curtail_pt)
                # TODO: catch errors.
                result = self.vip.rpc.call('platform.actuator', 'set_point',
                                           agent_id, curtailed_point,
                                           curtail_val).get(timeout=10)
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
    utils.vip_main(ahp)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

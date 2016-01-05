import re
import sys
import logging
from pandas import DataFrame as df
import numpy as np
from dateutil.parser import parse
from datetime import timedelta as td, datetime as dt
from copy import deepcopy
# from _ast import comprehension
from sympy import *
from sympy.parsing.sympy_parser import parse_expr
from collections import defaultdict
import abc
from collections import deque

# from volttron.platform.agent import utils, matching, sched
# from volttron.platform.messaging import headers as headers_mod,
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.agent.utils import jsonapi, setup_logging
from volttron.platform.vip.agent import Agent
from ilc.ilc_matrices import (extract_criteria, calc_column_sums,
                              normalize_matrix, validate_input,
                              history_data, build_score, input_matrix)


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

    def __init__(self, operation, minimum=None, maximum=None):
        self.min_func = lambda x: x if minimum is None else lambda x: min(x, minimum)
        self.max_func = lambda x: x if maximum is None else lambda x: max(x, maximum)
        self.minimum = minimum
        self.maximum = maximum
        self.operation = operation

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
    
    def ingest_data(self, data):
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
    
    def ingest_data(self, data):
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
    
    def ingest_data(self, data):
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
        
        pre_value, pre_timestamp = self.history.pop()

        if pre_timestamp > self.history_time:
            self.history.append((pre_value, pre_timestamp))
            return self.minimum

        post_value,  post_timestamp = self.history.pop()

        while post_timestamp < self.history_time:
            pre_value, pre_timestamp = post_value, post_timestamp
            post_value,  post_timestamp = self.history.pop()

        self.history.append((post_value,  post_timestamp))
        prev_value = self.linear_interpolation(pre_timestamp, pre_value,
                                               post_timestamp, post_value,
                                               self.history_time)
        if self.comparison_type == 'direct':
            val = abs(prev_value - self.current_value)
        elif self.comparison_type == 'inverse':
            val = 1/abs(prev_value - self.current_value)
        return val
    
    def ingest_data(self, data):
        current_time = dt.now()
        self.history_time = current_time - self.previous_time_delta
        self.current_value = data[self.point_name]
        self.history.appendleft((current_time, self.current_value))


class Criteria(object):
    def __init__(self, criteria):
        self.criteria = {}
        criteria = deepcopy(criteria)

        self.curtailment = criteria.pop("curtail")
        self.curtail_count = 0

        for name, criterion in criteria:
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
    
    def ingest_data(self, data):
        for criterion in self.criteria.values():
            criterion.ingest(data)
        
    def reset_curtail(self):
        self.curtail_count = 0
        
    def increment_curtail(self):
        self.curtail_count += 1
        
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
            
    def ingest_data(self, data):
        for criteria in self.all_criteria:
            criteria.ingest_data(data)
        
        for command in self.command_status:
            self.command_status[command] = bool(data[command])
            
    def reset_curtail(self):
        for criteria in self.criteria.values():
            criteria.reset_curtail()
            
    def evaluate(self, command):
        return self.criteria[command].evaluate()
    
    def get_curtailment(self, command):
        self.criteria[command].get_curtailment()
        
    def get_off_commands(self):
        return [command for command, state in self.command_status.iteritems() if not state]
    
    def get_on_commands(self):
        return [command for command, state in self.command_status.iteritems() if state]


def ahp(config_path, **kwargs):
    '''Intelligent Load Curtailment Algorithm'

    using Analytical Hierarchical Process.
    '''
    config = utils.load_config(config_path)
    location = {}
    location['campus'] = config.get('campus')
    location['building'] = config.get('building')
    device_configs = config['devices']
    all_devices = devices.keys()
    agent_id = config.get('agent_id')
#     base_device = "devices/{campus}/{building}/".format(campus=config.get('campus',''),
#                                                         building=config.get('building',''))
                                                        
    base_device_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''), 
                                            building=config.get('building', ''), 
                                            unit=None,
                                            path='',
                                            point='')
                                                        
    device_topic_list = []
    device_topic_map = {}
    for device_name in all_devices:
        device_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''), 
                                            building=config.get('building', ''), 
                                            unit=device_name,
                                            path='',
                                            point='all')
        device_topic_list.append(device_topic)
        device_topic_map[device_topic] = device_name
    
    power_token = config['PowerMeter']
    power_meter = power_token['device']
    power_pt = power_token['point']
    power_meter_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''), 
                                            building=config.get('building', ''), 
                                            unit=power_meter,
                                            path='',
                                            point=power_pt)
    
    
    

    demand_limit = float(config.get("demand_limit"))
    curtail_time = td(minutes=config.get("curtailment_time", 15.0))
    
    curtail_confirm = td(minutes=config.get("curtail_confirm", 15.0))
    
    
    devices = {}
    for device_name, device_config in device_configs:
        devices[device_name] = Device(device_config)
    
    global mappers
    
    try:
        mappers = config['mappers']
    except KeyError:
        mappers = {}

    class AHP(Agent):
        def __init__(self, **kwargs):
            super(AHP, self).__init__(**kwargs)
            self.off_dev = None
            self.running_ahp = False
            self.crit_labels = None
            self.row_average = None
            self.bldg_power = None
            self.transition = False
            self.remaining_device = None
            # self.start_up = True
            self.data_trender = None
            self.curtail_start = None
            
            excel_file = config['builing_criteria_matrix']
            self.crit_labels, criteria_arr = extract_criteria(excel_file, "CriteriaMatrix")
            col_sums = calc_column_sums(criteria_arr)
            _, self.row_average = normalize_matrix(criteria_arr, col_sums)
            print self.crit_labels, criteria_arr
            
            if not (validate_input(criteria_arr, col_sums, True,
                                   self.crit_labels, CRITERIA_LABELSTRING,
                                   MATRIX_ROWSTRING)):
                _log.info('Inconsistent criteria matrix. Check configuration '
                          'in ahp.xls file')
                # TODO:  MORE USEFULT MESSAGE TO DEAL WITH
                # INCONSISTENT CONFIGURATIONl
                sys.exit()

        @Core.receiver("onstart")
        def starting_base(self, sender, **kwargs):
            '''startup method:
             - Extract Criteria Matrix from excel file.
             - Setup subscriptions to device and building power meter.
            '''
            # Setup pubsub to listen to all devices being published.
            driver_prefix = topics.DRIVER_TOPIC_BASE
            _log.debug("subscribing to {}".format(driver_prefix))

            for device_topic in device_topic_list:
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=device_topic,
                                          callback=self.new_data)
                                          
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=power_meter_topic,
                                      callback=self.load_message_handler)

        def new_data(self, peer, sender, bus, topic, headers, message):
            '''Generate static configuration inputs for

            priority calculation.
            '''
            _log.info('Data Received')
            
            # topic of form:  devices/campus/building/device
            device = device_topic_map[topic]
            
            data = message[0]
            devices[device].ingest_data(data)
                
        def load_message_handler(self, peer, sender, bus, topic, headers, message):
            _log.debug('Reading building power data.')
            bldg_power = float(message[0])
            
            if self.running_ahp:
                now = dt.now()
                if now > self.curtail_start + curtail_confirm:
                    self.curtail_confirm(bldg_power)                
                return
            
            self.check_load(bldg_power)
                
        def check_load(self, bldg_power):
            '''Check whole building power and if the value is above the

            the demand limit (demand_limit) then initiate the AHP sequence.
            '''
            _log.debug('Checking building load.')
            
            if bldg_power > demand_limit:
                self.curtail_start = dt.now()
                self.running_ahp = True
                
                device_evaluations = self.get_all_device_evaluations()
                self.off_devices = self.get_off_devices()
                
                if not device_evaluations:
                    _log.info('All devices are off, nothing to curtail.')
                    return
                input_arr = input_matrix(device_evaluations, self.crit_labels)
                score_order = build_score(input_arr, self.row_average)
                self.remaining_devices = self.actuator_request(score_order)
                self.curtail(bldg_power)
                
            
            # TODO: Update below to verify on/off status
#             if device not in self.off_dev.keys():
#                 return    
            
        def curtail(self, bldg_power):
            '''Curtail loads by turning off device (or device components'''
            dev_keys = self.builder.keys()
            dev_keys = [(item.split('_')[0], item.split('_')[-1]) for item in dev_keys]
            dev_keys = [(item[0], item[-1]) for item in dev_keys if item[0] in self.remaining_devices]
            need_curtailed = bldg_power - demand_limit
            est_curtailed = 0.0
            for item in dev_keys:
                pt = static_config[item[0]][item[-1]]
                pt = pt.get('curtail', None)
                if pt is None:
                    raise Exception('The curtail section for {} is missing or '
                                    'or configured incorrectly.'.format(item))
                curtail_pt = pt.get('point', None)
                curtail_val = pt.get('value', None)
                curtail_load = pt.get('load', None)
                curtail_path = ''.join([location, item[0], curtail_pt])
                result = self.vip.rpc.call('platform.actuator', 'set_point',
                                           agent_id, curtail_path,
                                           curtail_val).get(timeout=10)
                est_curtailed += curtail_load
                self.no_curtailed[dev_keys] += 1.0
                self.remaining_devices.remove(item)
                if est_curtailed >= need_curtailed:
                    break
            self.transition = True
        
        def get_all_device_evaluations(self):
            results = {}
            for name, device in devices:
                for command in device.get_on_commands():
                    evaluations = device.evaluate(command)
                    results[name+'_'+command] = evaluations
            return results
        
        def get_off_devices(self):
            results = []
            for name, device in devices:
                results.extend((name+'_'+command for command in device.get_off_commands()))
                   
            return results 

        def curtail_confirm(self, cur_pwr):
            '''Check if load shed goal is met.'''
            saved_off = deepcopy(self.off_dev)
            if cur_pwr < demand_limit:
                _log.info('Curtail goal for building load met.')
            else:
                #self.device_status(check_only=True)
                if saved_off == self.off_dev and self.remaining_device:
                    self.curtail(self.remaining_device, cur_pwr)
                elif saved_off == self.off_dev:
                    _log.info('Did not meet load curtailment goal but there '
                              'are no further available loads to curtail.')
                else:
                    self.check_load(cur_pwr)    
        
        def actuator_request(self, score_order):
            '''request access to devices.'''
            _now = dt.now()
            str_now = _now.strftime(DATE_FORMAT)
            _end = _now + td(minutes=curtail_time + 5)
            str_end = _end.strftime(DATE_FORMAT)
            ctrl_dev = []
            for dev in score_order:
                curtailed_device = base_device_topic(unit=dev)
                schedule_request = [[curtailed_device, str_now, str_end]]
                result = self.vip.rpc.call(
                    'platform.actuator', 'request_new_schedule', agent_id,
                    agent_id, 'HIGH', schedule_request).get(timeout=10)
                if result['result'] == 'FAILURE':
                    _log.warn("Failed to schedule device: ", dev)
                else:
                    ctrl_dev.append(dev)
            return ctrl_dev



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

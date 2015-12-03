import re
import sys
import logging
import pandas as pd
from pandas import DataFrame as df
import numpy as np
from dateutil.parser import parse
import datetime
from datetime import timedelta as td, datetime as dt
from copy import deepcopy
from _ast import comprehension
from sympy import *
from sympy.parsing.sympy_parser import parse_expr
from collections import defaultdict
from ilc_matrices import (open_file, extract_criteria,
                          calc_column_sums, normalize_matrix,
                          validate_input, build_score, input_matrix)
 
from volttron.platform.agent import utils, matching, sched
from volttron.platform.messaging import headers as headers_mod, topics
from volttron.platform.agent.utils import jsonapi, setup_logging
from volttron.platform.vip.agent import *

MATRIX_ROWSTRING = "%20s\t%12.2f%12.2f%12.2f%12.2f%12.2f"
CRITERIA_LABELSTRING = "\t\t\t%12s%12s%12s%12s%12s"
DATE_FORMAT = '%m-%d-%y %H:%M:%S'
TESTING = True
setup_logging()
_log = logging.getLogger(__name__)


class DeviceTrender:
    def __init__(self, device_list):
        self.data = []
        self.data_arr = None
        self.pt_names = []
        self._master_devices = deepcopy(device_list)

    def reinit(self):
        self.data_arr = None
        self.data = []
        self.pt_names = []

    def new_data(self, device, points, data):
        '''Assemble dataframe containing device data'''
        self.pt_names.extend([(device + '_' + pt) for pt in points])
        self.data.extend(data[device][pt] for pt in points)

        if TESTING:
            cur_time = parse(
                data.get('date'), fuzzy=True).replace(second=0,
                                                      microsecond=0)
            self.ts = cur_time
        else:
            self.ts.append(dt.now().replace(second=0, microsecond=0))

        try:
            self.needs_devices.remove(device)
        except ValueError:
            '''Deal with missing data'''
            pass

        if (self.frame_data() if not self.needs_devices else False):
            return

        def frame_data(self):
            data_arr = df([self.data], columns=self.p_names, index=[self.ts])
            if self.data_arr is None:
                self.data_arr = data_arr
                self.needs_devices = deepcopy(self._master_devices)
                self.p_names = []
                self.data = []
                self.ts = []
                return 1
            self.needs_devices = deepcopy(self._master_devices)
            self.data_arr = self.data_arr.append(data_arr)
            self.p_names = []
            self.data = []
            self.ts = []
            return 0


def ahp(config_path, **kwargs):
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.debug,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%y %H:%M:%S')
    config = utils.load_config(config_path)
    location = dict((key, config['device'][key])
                    for key in ['campus', 'building'])
    devices = config['device']['unit']
    agent_id = config.get('agent_id')
    base_device = "devices/{campus}/{building}/".format(**location)
    power_token = config.get('PowerMeter', None)
    assert power_token
    power_dev = power_token.get('device', None)
    power_pt = power_token.get('point', None)
    if power_token is None or power_pt is None:
        raise Exception('PowerMeter section of configuration '
                        'file is not configured correctly.')
    units = devices.keys()
    devices_topic = (
        base_device + '({})(/.*)?/all$'
        .format('|'.join(re.escape(p) for p in units)))
    bld_pwr_topic = (
        base_device + '({})(/.*)?/all$'
        .format('|'.join(re.escape(p) for p in [power_dev])))
    BUILDING_TOPIC = re.compile(bld_pwr_topic)
    ALL_DEV = re.compile(devices_topic)
    static_config = config['device']
    all_devices = static_config.keys()
    no_curt = {}
    by_mode = static_config.get('by_mode')
    if by_mode is None:
        raise Exception('by_mode section of configuration file is missing.')
    demand_limit = float(config.get("Demand Limit"))
    curtail_time = float(config.get("Curtailment Time", 15.0))
    for key in static_config:
        for item in by_mode:
            no_curt[''.join([key, '_', item])] = 0

    class AHP(Agent):
        def __init__(self, **kwargs):
            super(AHP, self).__init__(**kwargs)
            self.off_dev = defaultdict(list)
            self.running_ahp = False
            self.builder = defaultdict(dict)
            self.crit_labels = None
            self.row_average = None
            self.failed_control = []
            self.bldg_power = None
            self.transition = False
            self.remaining_device = None
            self.no_curtailed = no_curt

        @Core.receiver("onstart")
        def starting_base(self, sender, **kwargs):
            self.data_trender = DeviceTrender(all_devices)
            reset_time = dt.now().replace(minute=0, hour=0,
                                          second=0, microsecond=0)
            reset_time = reset_time + td(days=1)
            self.core.schedule(reset_time, self.data_trender.reinit)
            excel_file = config.get('excel_file', None)

            if self.excel_file is not None:
                self.crit_labels, criteria_arr = \
                    extract_criteria(excel_file, "CriteriaMatrix")
                col_sums = calc_column_sums(criteria_arr)
                _, self.row_average = normalize_matrix(criteria_arr, col_sums)
                print self.crit_labels, criteria_arr
            if not (validate_input(criteria_arr, col_sums, True,
                                   self.crit_labels, CRITERIA_LABELSTRING,
                                   MATRIX_ROWSTRING)):
                _log.info('Inconsistent criteria matrix. Check configuration '
                          'in ahp.xls file')
                # TODO:  MORE USEFULT MESSAGE TO DEAL WITH
                # INCONSISTENT CONFIGURATION
                sys.exit()
            # Setup pubsub to listen to all devices being published.
            driver_prefix = topics.DRIVER_TOPIC_BASE
            _log.debug("subscribing to {}".format(driver_prefix))

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=driver_prefix,
                                      callback=self.new_data)

        def new_data(self, peer, sender, bus, topic, headers, message):
            '''Generate static configuration inputs for priority calculation.
            '''
            _log.info('Data Received')
            if ALL_DEV.match(topic):
                device = topic.split('/')[3]
                dev_config = static_config.get(device, None)
                if dev_config is None:
                    raise Exception('device section of configuration file '
                                    'for {} is mis-configured.'.format(device))
                point_list = dev_config.get('points', None)
                if point_list is None:
                    raise Exception('point_list section of configuration '
                                    'file for {} is missing.'.format(device))
                data = self.query_device(device, point_list)
                self.data_trender.new_data(key, point_list, data)
            if self.transition:
                return
            if self.start_up:
                return
            if BUILDING_TOPIC.match(topic) and not self.running_ahp:
                _log.debug('Reading building power data.')
                self.check_load(headers, message)
            if self.running_ahp:
                device = topic.split('/')[3]
            if device not in self.off_dev.keys():
                return

        def device_status(self):
            '''Query Actuator agent for current state of pertinent points on

            curtailable device.
            '''
            for key in static_config:
                dev_config = static_config.get(key, None)
                if dev_config is None:
                    raise Exception('device section of configuration file '
                                    'for {} is mis-configured.'.format(key))
                point_list = dev_config.get('points', None)
                if point_list is None:
                    raise Exception('point_list section of configuration '
                                    'file for {} is missing.'.format(key))
                device = None
                by_mode = dev_config.get('by_mode', None)
                if dev_config is None:
                    raise Exception('by_mode section of configuration '
                                    'file for {} is missing.'.format(key))
                for dev, status in by_mode.items():
                    check_status = self.vip.rpc.call(
                        'platform.actuator', 'get_point',
                        ''.join([location, key, status])).get(timeout=10)
                    if int(check_status[status]):
                        device = dev_config.get(dev, None)
                        break
                if device is None:
                    self.off_dev.update({key: by_mode.values()})
                    continue
                data = self.query_device(key, point_list)
                for sub_dev in device:
                    if data[sub_dev]:
                        self.construct_input(key, sub_dev,
                                             device[sub_dev], data)
                    else:
                        self.off_dev[key].append(sub_dev)

        def query_device(self, device, point_list):
            data = {}
            for point in point_list:
                value = self.vip.rpc.call(
                    'platform.actuator', 'get_point',
                    ''.join([location, device, point])).get(timeout=10)
                data.update({device: {point: value}})
            data[device].update({'date': dt.now()})
            return data

        def construct_input(self, key, sub_dev, criteria, data):
            '''Declare and construct data matrix for device.'''
            dev_key = ''.join([key, '_', sub_dev])
            self.builder.update({dev_key: {}})
            data = data[key]
            for item in criteria:
                if item == 'curtail':
                    continue
                _name = criteria.get('name', None)
                op_type = criteria.get('operation_type', None)
                _operation = criteria.get('operation', None)
                op_str = isinstance(op_type, str)
                op_lst = isinstance(op_type, list)
                if _name is None or op_type is None or _operation is None:
                    _log.error('{} is misconfigured.'.format(item))
                    raise Exception('{} is misconfigured'.format(item))
                if op_str and op_type == "constant":
                    val = criteria['operation']
                    if val < criteria['minimum']:
                        val = criteria['minimum']
                    if val > criteria['maximum']:
                        val = criteria['maximum']
                    self.builder[dev_key].update({_name: val})
                    continue
                if op_lst and op_type and op_type[0] == 'mapper':
                    val = config['mapper-' + op_type[1]][_operation]
                    if val < criteria['minimum']:
                        val = criteria['minimum']
                    if val > criteria['maximum']:
                        val = criteria['maximum']
                    self.builder[dev_key].update({_name: val})
                    continue
                if op_lst and op_type and op_type[0] == 'status':
                    if data[op_type[1]]:
                        val = _operation
                    else:
                        val = 0
                    self.builder[dev_key].update({_name: val})
                    continue
                if op_lst and op_type and op_type[0][0] == 'staged':
                    val = 0
                    for i in range(1, op_type[0][1]+1):
                        if data[op_type[i][0]]:
                            val += op_type[i][1]
                    if val < criteria['minimum']:
                        val = criteria['minimum']
                    if val > criteria['maximum']:
                        val = criteria['maximum']
                    self.builder[dev_key].update({_name: val})
                    continue
                if op_lst and op_type and op_type[0] == 'formula':
                    _points = op_type[1].split(" ")
                    points = symbols(op_type[1])
                    expr = parse_expr[_operation]
                    pt_lst = []
                    for item in _points:
                        pt_lst.append([(item, data[item])])
                    val = expr.subs([pt_lst])
                    if val < criteria['minimum']:
                        val = criteria['minimum']
                    if val > criteria['maximum']:
                        val = criteria['maximum']
                    self.builder[dev_key].update({_name: val})
                    continue
                if op_lst and op_type and op_type[0] == 'history':
                    pt_name = op_type[1]
                    _now = dt.now().replace(second=0, microsecond=0)
                    comp_time = int(op_type[2])
                    prev = _now - td(minutes=comp_time)
                    prev_val = self.data_trender.data_arr[dev_key].ix[prev]
                    cur_val = data[pt_name]
                    if _operation == 'direct':
                        val = abs(prev_val - cur_val)
                    elif _operation == 'inverse':
                        val = 1/abs(prev_val-cur_val)
                    if val < criteria['minimum']:
                        val = criteria['minimum']
                    if val > criteria['maximum']:
                        val = criteria['maximum']
                    self.builder[dev_key].update({_name: val})
                    continue
            self.builder[dev_key].update(
                {'no_curtailed': self.no_curtailed[dev_key]})

        def check_load(self, headers, message):
            '''Check whole building power and if the value is above the

            the demand limit (demand_limit) then initiate the AHP sequence.
            '''
            obj = jsonapi.loads(message[0])
            bldg_power = float(obj[power_pt])
            if bldg_power > demand_limit:
                self.bldg_power = bldg_power
                self.running_ahp = True
                self.device_status()
                input_arr = input_matrix(self.builder, self.crit_labels)
                scores, score_order = build_score(input_arr, self.row_average)
                ctrl_dev = self.actuator_request(score_order)
                self.remaining_device = deepcopy(ctrl_dev)
                self.curtail(ctrl_dev, scores, score_order)

        def actuator_request(self, score_order):
            '''request access to devices.'''
            _now = dt.now()
            str_now = _now.strftime(DATE_FORMAT)
            _end = _now + td(minutes=curtail_time + 5)
            str_end = _end.strftime(DATE_FORMAT)
            schedule_request = []
            for dev in score_order:
                curtailed_device = ''.join([base_device, dev])
                schedule_request = [[curtailed_device, str_now, str_end]]
                result = self.vip.rpc.call(
                    'platform.actuator', 'request_new_schedule', agent_id,
                    agent_id, 'HIGH', schedule_request).get(timeout=10)
                if result['result'] == 'FAILURE':
                    self.failed_control.append(dev)
            ctrl_dev = [dev for dev in score_order if dev not in self.failed_control]
            return ctrl_dev

        def curtail(self, ctrl_dev, scores, score_order):
            dev_keys = self.builder.keys()
            dev_keys = [(item.split('_')[0], item.split('_')[-1]) for item in dev_keys]
            dev_keys = [(item[0], item[-1]) for item in dev_keys if item[0] in ctrl_dev]
            need_curtailed = self.bldg_power - demand_limit
            est_curtailed = 0.0
            for item in dev_keys:
                pt = static_config[item[0]][item[-1]]
                pt = pt.get('curtail', None)
                if pt is None:
                    _log.error('The "curtail" section of device configuration '
                               'is missing or configured incorrectly')
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
                self.remaining_device.remove(item)
                if est_curtailed >= need_curtailed:
                    break
            self.transition == True
            _chk_time = dt.now() + td(minutes=5)
            self.core.schedule(_chk_time, self.curtailed_power)

        def curtailed_power(self):
            pwr_mtr = ''.join([location, power_dev, power_pt])
            value = self.vip.rpc.call('platform.actuator', 'get_point',
                                      pwr_mtr).get(timeout=10)
            cur_pwr = value[power_pt]
            if value[cur_pwr] < demand_limit:
                pass
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
import sys
import logging
import datetime

from volttron.lite.agent import BaseAgent, periodic, PublishMixin
from volttron.lite.agent.utils import jsonapi
from volttron.lite.agent import utils
from volttron.lite.agent.matching import match_glob, match_headers, match_exact, match_start
from volttron.lite.messaging import headers as headers_mod, topics

from xlrd import open_workbook
from ahp import calc_column_sums, validate_input, demo_ahp

import time

utils.setup_logging()
_log = logging.getLogger(__name__)

# Variables that are only used for output to file for demo period
criteria_labels = ['NO_curtailing', 'deltaT_zone_delta', 'Room_rtu', 'Power_rtu', 'deltaT_zone_sp']
matrix_rowstring = "%20s\t%15.2f%19.2f%10.2f%11.2f%16.2f"
criteria_labelstring = "\t\t\t%15s%19s%10s%11s%16s"


class LoggerWriter:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, message):
        if message != '\n':
            self.logger.log(self.level, message)


# Function to extract the criteria matrix from the CriteriaMatrix sheet of the excel spreadsheet
def extract_criteria_matrix(excel_file):
    # Open the excel file
    wb = open_workbook(excel_file)

    # Access the "CriteriaMatrix" sheet
    sheet = wb.sheet_by_name("CriteriaMatrix")

    criteria_labels = []
    criteria_matrix = []
    # Matrix starts at row 3 (column headers, which are duplicated by column A) and runs until "Column Sum"
    for row in range(3, sheet.nrows):
        if(sheet.cell(row, 0).value == "Column Sum"):
            break

        criteria_labels.append(sheet.cell(row, 0).value)

    # NOTE: the number of rows and number of columns should match
    # Iterate over the rows and columns of the spreadsheet loading the numbers as floating point values into a list of lists.
    for row in range(3, 3 + len(criteria_labels)):
        temp_row = []
        for col in range(1, 1 + len(criteria_labels)):
            temp_row.append(float(sheet.cell(row, col).value))
        criteria_matrix.append(temp_row)

    return criteria_labels, criteria_matrix


class Reading(object):
    """docstring for Reading"""
    def __init__(self, timestamp, cooling_setpoint, heating_setpoint, temperature):
        super(Reading, self).__init__()
        self.timestamp = timestamp
        self.cooling_setpoint = cooling_setpoint
        self.heating_setpoint = heating_setpoint
        self.temperature = temperature

    def diffHeating(self):
        return self.temperature - self.heating_setpoint

    def diffCooling(self):
        return self.temperature - self.cooling_setpoint

    def printValues(self):
        print "Timestamp:", self.timestamp
        print 'CoolingSetpoint:', self.cooling_setpoint
        print 'HeatingSetpoint:', self.heating_setpoint
        print 'ZoneTemperature:', self.temperature


class DeviceData(object):
    """docstring for DeviceData"""
    def __init__(self, device, points):
        super(DeviceData, self).__init__()
        self.device = device
        self.points = points
        self.readings = []
        self.currentReading = None
        self.lastReading = None
        self.roomRTU = 3
        self.power = 7
        self.offset = 0.0
        self.curtailed = False
        # seed()
        self.curtailmentCount = 0  # randint(0, 25)
        self.curtailmentAllowed = True

    def process_data(self, timestamp, data):
        self.lastReading = self.currentReading
        self.currentReading = Reading(timestamp,
                                      float(data[self.points['CoolingSetpoint']]),
                                      float(data[self.points['HeatingSetpoint']]),
                                      float(data[self.points['ZoneTemperature']]) + self.offset)
        if self.curtailed:
            self.offset += .25
        elif self.currentReading.temperature + self.offset != self.currentReading.temperature:
            self.offset -= .25

        self.readings.append(self.currentReading)
        # self.currentReading.printValues()

    def generateMatrixRow(self):
        return [self.curtailmentCount, 1.0/max(1, (self.lastReading.temperature - self.currentReading.temperature)),
                self.roomRTU, self.power, 1.0 / max(1, self.currentReading.diffCooling())]

    def curtailWithThreshold(self):
        print "========= Curtailing " + self.device + " ================="

        if self.curtailmentAllowed:
            self.curtailmentCount += 1
            if self.curtailmentCount >= 10:
                self.curtailmentAllowed = False
            print 'yes'
            self.curtaled = True
            return True
        else:
            self.curtailmentCount -= 1
            if self.curtailmentCount == 0:
                self.curtailmentAllowed = True
            print 'no'
            self.curtailed = False
            return False

    def curtail(self):
        print "========= Curtailing " + self.device + " ================="
        self.curtailmentCount += 1
        print self.curtailmentCount
        return True


def generateMatrix(device_list, deviceDataHandlers):
    inputMatrix = []
    for deviceRow in device_list:
        inputMatrix.append(deviceDataHandlers[deviceRow[0]].generateMatrixRow())

    return inputMatrix


def AhpAgent(config_path, **kwargs):
    config = utils.load_config(config_path)
    agent_id = config['agentid']
    threshold = 14

    def get_config(name):
        try:
            value = kwargs.pop(name)
            return value
        except KeyError:
            return config[name]

    # This agent uses the implementation of the ahp agorithm to determine what (if any)
    # devices in a building are to be curtailed to shed electrical load. The criteria
    # matrix is expected to be in a table in an excel spredsheet (to simplify data entry by the end user)
    # The agent will listen for information being sent from the bacnet drivers regarding the desired
    # devices, and on a periodic basis (to be set in the configuration file) perform calculations to
    # select the device(s) that are candidates for curtailment. This initial implementation will
    # be focused on heat pumps in a commercial building. As a result, the agent will also need
    # to keep track of the times when the compressor was stopped to allow for a period of equilibrium.
    #
    # TODO:
    #   * Have the agent open and read the criteria matrix from the excel spreadsheet
    #   * Subscribe to the topics that provide the information from the bacnet drivers
    #   * Store the readings from the heat pumps that are to be watched

    class Agent(PublishMixin, BaseAgent):
        """Agent that performs curtailment in a building using the AHP algorithm"""
        def __init__(self, **kwars):
            super(Agent, self).__init__(**kwargs)

        def setup(self):
            # Load criteria matrix
            excel_doc = get_config("excel_doc")
            self.output_log = open("ahp_algorithm.log", "w")
            self.logger = LoggerWriter(_log, logging.DEBUG)

            self.logger.write("Testing")

            (self.criteria_labels, self.criteria_matrix) = extract_criteria_matrix(excel_doc)
            self.criteria_matrix_sums = calc_column_sums(self.criteria_matrix)

            # Validate criteria matrix
            if(not validate_input(self.criteria_matrix, self.criteria_matrix_sums, True, criteria_labels, criteria_labelstring, matrix_rowstring, display_dest=self.logger)):
                # TODO: log a warning indicatin invalid matrix input
                pass

            # TODO: Load device list. Right now, it will come from the config file.
            #       Eventually this will come from the excel spreadsheet
            self.device_list = [['HP5', {'ZoneTemperature': 'RMTEMP', 'HeatingSetpoint': 'SETPOINT', 'CoolingSetpoint': 'ClgSETPOINT'}],
                                ['HP8', {'ZoneTemperature': 'RMTEMP', 'HeatingSetpoint': 'SETPOINT', 'CoolingSetpoint': 'ClgSETPOINT'}],
                                ['HP3', {'ZoneTemperature': 'RMTEMP', 'HeatingSetpoint': 'SETPOINT', 'CoolingSetpoint': 'ClgSETPOINT'}],
                                ['HP2', {'ZoneTemperature': 'RMTEMP', 'HeatingSetpoint': 'SETPOINT', 'CoolingSetpoint': 'ClgSETPOINT'}],
                                ['HP7', {'ZoneTemperature': 'RMTEMP', 'HeatingSetpoint': 'SETPOINT', 'CoolingSetpoint': 'ClgSETPOINT'}]]

            self.deviceLabels = [row[0] for row in self.device_list]
            self.deviceDataHandlers = {}
            for deviceRow in self.device_list:
                self.deviceDataHandlers[deviceRow[0]] = DeviceData(deviceRow[0], deviceRow[1])
            super(Agent, self).setup()

        # TODO: Set up subscriptions. Need to subscribe to sigma4/all
        @match_glob('RTU/PNNL/BOCC/Sigma4/HP*/all')
        def process_data(self, topic, headers, message, match):
            data = jsonapi.loads(message[0])
            # print >> self.logger, topic, message

            device_label = topic.split('/')[4]

            if device_label in self.deviceDataHandlers:
            # look up device
                device = self.deviceDataHandlers[device_label]

                # call device process_data method
                device.process_data(time.time(), data)

        @periodic(600)
        def schedule_algorithm(self):
            # submit request for schedule to change points
            headers = {
                'AgentID': agent_id,
                'type':  'NEW_SCHEDULE',
                'requesterID': agent_id,
                'taskID': agent_id,
                'priority': 'LOW_PREEMPT'
            }

            # Build up schedule
            start = str(datetime.datetime.now())
            end = str(datetime.datetime.now() + datetime.timedelta(minutes=1))

            # msg = [['PNNL/BOCC/Sigma4/HP1', start, end]]
            msg = []
            for label in self.deviceLabels:
                msg.append(['PNNL/BOCC/Sigma4/' + label, start, end])

            print >> self.logger, "Submitting schedule"
            self.publish_json(topics.ACTUATOR_SCHEDULE_REQUEST(), headers, msg)
            print >> self.logger, "Schedule submitted"

            # Example from afddagent
            # self.task_timer = self.periodic_timer(60, self.publish_json, topics.ACTUATOR_SCHEDULE_REQUEST(), headers,[["{campus}/{building}/{unit}".format(**rtu_path),self.start,self.end]])

        @match_headers({headers_mod.REQUESTER_ID: agent_id})
        @match_exact(topics.ACTUATOR_SCHEDULE_RESULT())
        def handle_scheduler_response(self, topic, headers, message, match):
            msg = jsonapi.loads(message[0])
            response_type = headers.get('type', 0)

            if response_type == 'NEW_SCHEDULE':
                if msg.get('result', 0) == 'SUCCESS':
                    self.logger.write("Schedule Successful")
                    self.ready = True

        @match_headers({headers_mod.REQUESTER_ID: agent_id})
        @match_start('RTU/actuators/schedule/announce')
        def do_algorithm(self, topic, headers, message, match):
            if self.ready:
                self.ready = False
                print >> self.logger, "====== Calculate Curtailment ======"
                # The actual ahp algorithm stuff will happen as part of the response to a successful request for a schedule.

                device_matrix = generateMatrix(self.device_list, self.deviceDataHandlers)

                print >> self.logger, self.deviceDataHandlers
                scores = demo_ahp(self.criteria_matrix, device_matrix, self.deviceLabels, self.criteria_labels, criteria_labelstring, matrix_rowstring, display_dest=self.logger)
                # def demo_ahp(criteria_matrix, device_matrix, devices, criteria_labels="", criteria_labelstring="", matrix_rowstring="", display_dest=sys.stdout):
                pwr_saved = 0
                device_offsets = []
                for device in scores:
                    if pwr_saved >= threshold:
                        device_offsets.append(0.0)
                    else:
                        if self.deviceDataHandlers[device[0]].curtailWithThreshold():
                            device_offsets.append(3.0)
                        else:
                            device_offsets.append(0.0)

                        pwr_saved += 7

                header = {'requesterID': agent_id}
                device_count = 0
                for (device, score) in scores:
                    path = 'RTU/actuators/set/PNNL/BOCC/Sigma4/' + device + '/Volttron_Temp_Offset'
                    print >> self.logger, 'Updating %s with %d' % (path, device_offsets[device_count])
                    self.publish(path, header, str(device_offsets[device_count]))
                    device_count += 1

                headers = {
                    'AgentID': agent_id,
                    'type':  'CANCEL_SCHEDULE',
                    'requesterID': agent_id,
                    'taskID': agent_id,
                }

                self.publish_json(topics.ACTUATOR_SCHEDULE_REQUEST(), headers, [])

            else:
                self.ready = False



    Agent.__name__ = 'AhpAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(AhpAgent,
                       description='VOLTTRON Lite™ ahp algorithm agent',
                       argv=argv)


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        pass

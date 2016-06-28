import datetime
from math import sin, cos, pi
from volttron.platform.vip.agent import Agent, RPC, Core
from volttron.platform.agent import utils

# The 'connector' api has a hyphen in its name
# so we have to add it the the python search path
# before we can import it. If you've installed it
# a different way this may change.
import sys
sys.path.insert(0, './ddsagent/rticonnextdds-connector')
import rticonnextdds_connector as rti

class DDSAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(DDSAgent, self).__init__(**kwargs)

        self.reader = {}
        self.writer = {}

        config = utils.load_config(config_path)

        for typename, type_config in config.iteritems():
            participant_name = type_config['participant_name']
            xml_config_path = type_config['xml_config_path']
            publisher_name = type_config['publisher_name']
            subscriber_name = type_config['subscriber_name']
            connector = rti.Connector(participant_name, xml_config_path)

            self.writer[typename] = connector.getOutput(publisher_name)
            self.reader[typename] = connector.getInput(subscriber_name)

    @Core.periodic(1)
    def publish_demo(self):
        sample = {"shapesize": 30,
                  "color": "BLUE"}

        center = 100
        radius = 50
        now = datetime.datetime.now()
        radians = pi * float(now.second) / 15.0

        sample['x'] = center + int(radius * cos(radians))
        sample['y'] = center + int(radius * sin(radians))

        self.write_to_dds('square', sample)

    @RPC.export
    def read_from_dds(self, typename):
        reader = self.reader[typename]

        # A data access method must be called before we can
        # examine `samples` in the vernacular of DDS.
        # .read() does not modify the reader's receive queue
        # .take() removes data from reader's receive queue
        reader.read()

        # For this example we'll return all samples we can see
        samples = []

        # Find out how many samples we have so
        # they can be explicitly indexed
        n_samples = reader.samples.getLength()

        # Indexes start at one. Yuck.
        for i in range(1, n_samples + 1):
            if reader.infos.isValid(i):
                # Struct fields can be retrieved as a dict
                # or accessed individually. A dictionary
                # will be easier in most cases.
                d = reader.samples.getDictionary(i)
                samples.append(d)

        return samples

    @RPC.export
    def write_to_dds(self, typename, sample):
        writer = self.writer[typename]

        # We can write an entire dictionary or set
        # struct fields individually. A dictionary
        # will be easier in most cases.
        writer.instance.setDictionary(sample)

        # Send the new data to DDS.
        writer.write()


def main():
    utils.vip_main(DDSAgent)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

from volttron.platform.vip.agent import Agent, RPC
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

        config = utils.load_config(config_path)

        participant_name = config['participant_name']
        xml_config_path = config['xml_config_path']
        publisher_name = config['publisher_name']
        subscriber_name = config['subscriber_name']

        connector = rti.Connector(participant_name, xml_config_path)
        self.writer = connector.getOutput(publisher_name)
        self.reader = connector.getInput(subscriber_name)

    @RPC.export
    def read_from_dds(self):
        # A data access method must be called before we can
        # examine `samples` in the vernacular of DDS.
        # .read() does not modify the reader's receive queue
        # .take() removes data from reader's receive queue
        self.reader.read()

        # For this example we'll return all samples we can see
        samples = []

        # Find out how many samples we have so
        # they can be explicitly indexed
        n_samples = self.reader.samples.getLength()

        # Indexes start at one. Yuck.
        for i in range(1, n_samples + 1):
            if self.reader.infos.isValid(i):
                # Struct fields can be retrieved as a dict
                # or accessed individually. A dictionary
                # will be easier in most cases.
                d = self.reader.samples.getDictionary(i)
                samples.append(d)

        return samples

    @RPC.export
    def write_to_dds(self, sample):
        # We can write an entire dictionary or set
        # struct fields individually. A dictionary
        # will be easier in most cases.
        self.writer.instance.setDictionary(sample)

        # Send the new data to DDS.
        self.writer.write()


def main():
    utils.vip_main(DDSAgent)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

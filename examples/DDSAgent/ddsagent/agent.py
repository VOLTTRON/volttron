# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import datetime
from math import sin, cos, pi
from volttron.platform.vip.agent import Agent, RPC, Core
from volttron.platform.agent import utils

# The 'connector' api doesn't come with a nice
# way to install itself so we have it added
# as a subtree here. Hopefully this will
# change in the future.
import sys
sys.path.insert(0, './ddsagent/rticonnextdds-connector-master')
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
        """
        Publish a square that follows a circular path.
        Can be visualized by running the *rtishapesdemo*
        program and subscribing to *square*.
        """

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
        """ RPC method

        Read samples from the DDS message bus.

        A data access method must be called before we can
        examine `samples` in the vernacular of DDS. This
        examples uses read(), which *does not* modify the
        reader's receive queue. The other option is take(),
        which *does* remove data from the receive queue.

        :param typename: Name of the type to read.
        :type typename: str
        :returns: samples available on the DDS message bus
        :rtype: list of dictionaries

        .. warning:: Attempting to read a type of **typename**
                     that was not in the config file will raise
                     KeyError.
        """

        reader = self.reader[typename]
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
        """ RPC method

        Write sample to the DDS message bus.

        :param typename: Name of the type to write.
        :type typename: str
        :param sample: Data to write to DDS bus.
        :type sample: dict

        .. warning:: Attempting to write to a type of **typename**
                     that was not in the config file will raise
                     KeyError.
        """

        writer = self.writer[typename]
        writer.instance.setDictionary(sample)
        writer.write()


def main():
    utils.vip_main(DDSAgent)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

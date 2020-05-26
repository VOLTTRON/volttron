# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import sys
import logging

from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian

import csv


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '1.0.1'


def historian(config_path, **kwargs):
    """
    This method is called by the main method to parse
    the passed config file or configuration dictionary object, validate the
    configuration entries, and create an instance of the CSVHistorian class
    :param config_path: could be a path to a configuration file or can be a dictionary object
    :param kwargs: additional keyword arguments if any
    :return: an instance of :py:class:`CSVHistorian`
    """
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)

    output_path = config_dict.get("output", "historian_output.csv")

    return CSVHistorian(output_path=output_path, **kwargs)


class CSVHistorian(BaseHistorian):
    """
    Historian that stores the data into crate tables.

    """

    def __init__(self, output_path="", **kwargs):
        self.output_path = output_path
        self.csv_dict = None
        self.csv_file = None
        super(CSVHistorian, self).__init__(**kwargs)

    def version(self):
        return __version__

    def publish_to_historian(self, to_publish_list):
        for record in to_publish_list:
            row = dict()
            row["timestamp"] = record["timestamp"]

            row["source"] = record["source"]
            row["topic"] = record["topic"]
            row["value"] = record["value"]

            self.csv_dict.writerow(row)

        self.report_all_handled()
        self.csv_file.flush()

    def historian_setup(self):
        self.csv_file = open(self.output_path, "w")
        self.csv_dict = csv.DictWriter(self.csv_file, fieldnames=["timestamp", "source", "topic", "value"])
        self.csv_dict.writeheader()
        self.csv_file.flush()


def main(argv=sys.argv):
    """Main method called by the eggsecutable.
    @param argv:
    """
    try:
        utils.vip_main(historian)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

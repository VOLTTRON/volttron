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

import logging
import sys

from volttron.platform.agent.base_historian import BaseHistorian, add_timing_data_to_header
from volttron.platform.agent import utils
from volttron.platform.agent import math_utils
from volttron.platform.vip.agent.core import Core

utils.setup_logging()
_log = logging.getLogger(__name__)


def historian(config_path, **kwargs):

    config = utils.load_config(config_path)
    utils.update_kwargs_with_config(kwargs, config)

    class NullHistorian(BaseHistorian):
        '''This historian forwards data to another platform.
        '''

        def __init__(self, **kwargs):
            super(NullHistorian, self).__init__(**kwargs)

            if self._gather_timing_data:
                self._turnaround_times = []

        @Core.receiver("onstart")
        def starting(self, sender, **kwargs):

            _log.debug('Null historian started.')

        def publish_to_historian(self, to_publish_list):

            for item in to_publish_list:
                if self._gather_timing_data:
                    turnaround_time = add_timing_data_to_header(item["headers"],
                                                                self.core.agent_uuid or self.core.identity,
                                                                "published")
                    self._turnaround_times.append(turnaround_time)
                    if len(self._turnaround_times) > 10000:
                        # Test is now over. Button it up and shutdown.
                        mean = math_utils.mean(self._turnaround_times)
                        stdev = math_utils.stdev(self._turnaround_times)
                        _log.info("Mean time from collection to publish: " + str(mean))
                        _log.info("Std dev time from collection to publish: " + str(stdev))
                        self._turnaround_times = []
                #_log.debug("publishing {}".format(item))

            _log.debug("recieved {} items to publish"
                       .format(len(to_publish_list)))

            self.report_all_handled()

        def query_historian(self, topic, start=None, end=None, agg_type=None,
              agg_period=None, skip=0, count=None, order="FIRST_TO_LAST"):
            """Not implemented
            """
            raise NotImplemented("query_historian not implimented for null historian")

    return NullHistorian(**kwargs)


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(historian, identity="nullhistorian")
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

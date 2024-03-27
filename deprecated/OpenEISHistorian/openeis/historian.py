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


import datetime
import logging
import sys
import requests
from requests import ConnectionError

from volttron.utils.docs import doc_inherit
from volttron.platform import jsonapi
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.1'


def historian(config_path, **kwargs):

    config = utils.load_config(config_path)
    connection = config.get('connection')

    assert connection
    assert connection.get('type') == 'openeis'

    params = connection.get('params')
    assert params

    uri = params.get('uri')
    assert uri

    login = params.get('login')
    assert login

    password = params.get('password')
    assert password
    # Auth will get passed to the server through the requests python framework.
    auth = (login, password)

    datasets = config.get("dataset_definitions")
    assert datasets
    assert len(datasets) > 0

    headers = {'content-type': 'application/json'}

    class OpenEISHistorian(BaseHistorian):
        '''An OpenEIS historian which allows the publishing of dynamic.

        This historian publishes to an openeis instance with the following
        example json payload:

        dataset_extension = {
            "dataset_id": dataset_id,
            "point_map":
            {
                "New building/WholeBuildingPower": [["2/5/2014 10:00",48.78], ["2/5/2014 10:05",50.12], ["2/5/2014 10:10",48.54]],
                "New building/OutdoorAirTemperature": [["2/5/2014 10:00",48.78], ["2/5/2014 10:05",10.12], ["2/5/2014 10:10",48.54]]
            }
        }

        The dataset must exist on the openeis webserver.  The mapping (defined)
        in the configuration file must include both the input (from device)
        topic and output (openeis schema topic).  See openeis.historian.config
        for a full description of how those are specified in the coniguration
        file.

        This service will publish to server/api/datasets/append endpoint.
        '''

        @doc_inherit
        def publish_to_historian(self, to_publish_list):
            _log.debug("publish_to_historian number of items: {}".format(len(to_publish_list)))

            # print(to_publish_list)
            dataset_uri = uri + "/api/datasets/append"

            # Build a payload for each of the points in each of the dataset definitions.
            for dsk, dsv in datasets.items():
                ds_id = dsv["dataset_id"]
                ds_points = dsv['points']  # [unicode(p) for p in dsv['points']]
                ignore_unmapped = dsv.get('ignore_unmapped_points', 0)

                point_map = {}
                try_publish = []
                for to_pub in to_publish_list:
                    for point in ds_points:
                        if to_pub['topic'] in point.keys():
                            try_publish.append(to_pub)
                            # gets the value of the sensor for publishing.
                            openeis_sensor = point[to_pub['topic']]
                            if not openeis_sensor in point_map:
                                point_map[openeis_sensor] = []

                            point_map[openeis_sensor].append([to_pub['timestamp'], to_pub['value']])
                        else:
                            if ignore_unmapped:
                                self.report_handled(to_pub)
                            else:
                                err = 'Point {topic} was not found in point map.'.format(**to_pub)
                                _log.error(err)

                    # pprint(point_map)

                if len(point_map) > 0:
                    payload = {'dataset_id': ds_id,
                               'point_map': point_map}
                    payload = jsonapi.dumps(payload, default=datetime.datetime.isoformat)
                    try:
                        # resp = requests.post(login_uri, auth=auth)
                        resp = requests.put(dataset_uri, verify=False, headers=headers, data=payload)
                        if resp.status_code == requests.codes.ok:
                            self.report_handled(try_publish)
                    except ConnectionError:
                        _log.error('Unable to connect to openeis at {}'.format(uri))
                        return
            '''
            Transform the to_publish_list into a dictionary like the following

            dataset_extension = {
                "dataset_id": dataset_id,
                "point_map":
                {
                    "New building/WholeBuildingPower": [["2/5/2014 10:00",48.78], ["2/5/2014 10:05",50.12], ["2/5/2014 10:10",48.54]],
                    "New building/OutdoorAirTemperature": [["2/5/2014 10:00",48.78], ["2/5/2014 10:05",10.12], ["2/5/2014 10:10",48.54]]
                }
            }
            '''

        @doc_inherit
        def historian_setup(self):
            # TODO Setup connection to openeis.
            pass

    OpenEISHistorian.__name__ = 'OpenEISHistorian'
    return OpenEISHistorian(config, **kwargs)


def main(argv=sys.argv):
    """
    Main method called by the eggsecutable.
    """
    try:
        utils.vip_main(historian, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

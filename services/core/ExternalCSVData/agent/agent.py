# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:


# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

from __future__ import absolute_import

import logging
import sys
import csv
import requests

from volttron.platform.messaging.utils import Topic

from ast import literal_eval

from StringIO import StringIO

from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

PUBLISH_TOPIC = Topic("{base}//{source}//{key}")

utils.setup_logging()
__author__ = 'Kyle Monson'
__copyright__ = 'Copyright (c) 2017, Battelle Memorial Institute'
__license__ = 'FreeBSD'

_log = logging.getLogger(__name__)
__version__ = '3.2'
DEFAULT_MESSAGE = ' Message'

def csv_agent(config_path, **kwargs):
    config = utils.load_config(config_path)
    sources = config.get('sources', [])
    interval = float(config.get('interval', 300.0))
    global_topic_prefix = config.get('global_topic_prefix', "")

    topic = PUBLISH_TOPIC(base=global_topic_prefix,
                          source=None,
                          key=None)

    return AgentCSV(interval, sources, topic, **kwargs)

class AgentCSV(Agent):
    """Gathers and publishes CSV data available via a web api.
    """

    def __init__(self, interval, sources, topic,**kwargs):
        super(AgentCSV, self).__init__(**kwargs)
        self.interval = interval
        self.sources = sources
        self.topic= topic

        self._validate_sources()

    def _validate_sources(self):
        #Simple validation of sources
        new_sources = []
        for source in self.sources:
            url = source.get("url")
            key_column = source.get("key")
            source_topic = source.get("topic", "")

            if url is None:
                _log.error("Missing url from source!")
                continue

            if not key_column is None:
                topic = self.topic(source=source_topic, key="")
                if not topic:
                    _log.error("{url} configured to publish without topic. Removing source".format(url=url))
                    continue

            new_sources.append(source)

        self.sources = new_sources


    @Core.receiver('onstart')
    def onstart(self,sender, **kwargs):
        self.core.periodic(self.interval, self.publish_data)

    def publish_data(self):

        now = utils.get_aware_utc_now()
        now = utils.format_timestamp(now)
        headers = {
                   headers_mod.DATE: now,
                    headers_mod.TIMESTAMP: now
                  }

        for source in self.sources:
            url = source.get("url")
            params = source.get("params")
            key_column = source.get("key", "")
            flatten = source.get("flatten", False)
            source_topic = source.get("topic", "")
            parse_columns = source.get("parse", [])

            _log.info("Grabbing data from " + url)

            try:
                r = requests.get(url, params=params)
                r.raise_for_status()
            except requests.exceptions.HTTPError as e:
                _log.error("Failure to read from source {url} {reason}".format(url=url, reason=str(e)))
                continue

            file_obj = StringIO(r.content)

            if flatten:
                to_flatten = csv.reader(file_obj)
                row_data = {}
                csv_rows_skipped = False
                for row in to_flatten:
                    try:
                        row_data[row[0]] = row[1]
                    except IndexError:
                        csv_rows_skipped = True
                if csv_rows_skipped:
                    _log.warning("Skipped incomplete flatten rows in {url}".format(url=url))

                csv_data = [row_data]

            else:
                csv_data = csv.DictReader(StringIO(r.content))

            if parse_columns:
                new_csv_data = []
                for row in csv_data:
                    for parse_column in parse_columns:
                        try:
                            value_string = row[parse_column]
                            value = literal_eval(value_string)
                            row[parse_column] = value
                        except KeyError:
                            pass
                        except StandardError:
                            if value_string == "":
                                row[parse_column] = None
                    new_csv_data.append(row)

                csv_data = new_csv_data

            if key_column:
                dropped_rows=False
                for row in csv_data:
                    key = row.pop(key_column, "")
                    topic = self.topic(source=source_topic, key=key)
                    if topic:
                        self.vip.pubsub.publish(peer='pubsub', topic=topic, message=row, headers=headers).get(
                            timeout=10.0)
                    else:
                        dropped_rows=True
                if dropped_rows:
                    _log.warning("Skipped rows with invalid topic from {url}".format(url=url))

            else:
                #The topic has already been verified as legit by now.
                topic = self.topic(source=source_topic, key="")
                if flatten:
                    data = csv_data[0]
                else:
                    data = csv_data
                self.vip.pubsub.publish(peer='pubsub', topic=topic, message=data, headers=headers).get(
                    timeout=10.0)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(csv_agent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ =='__main__':
    # Entry point for script
    sys.exit(main())

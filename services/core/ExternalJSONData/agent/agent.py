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

import datetime
import logging
import sys
import requests
from requests.auth import HTTPBasicAuth
import json
from volttron.platform.messaging.utils import Topic

from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

utils.setup_logging()
__author__ = 'Kyle Monson'
__copyright__ = 'Copyright (c) 2017, Battelle Memorial Institute'
__license__ = 'FreeBSD'

_log = logging.getLogger(__name__)
__version__ = '1.0'


PUBLISH_TOPIC = Topic("{base}//{source}//{key}")


def json_agent(config_path, **kwargs):
    config = utils.load_config(config_path)

    interval = config.get('interval', 300)
    default_user = config.get('default_user')
    default_password = config.get('default_password')
    global_topic_prefix = config.get('global_topic_prefix', "")
    topic = PUBLISH_TOPIC(base=global_topic_prefix,
                          source=None,
                          key=None)
    sources = config.get("sources", [])

    return ExternalJSON(interval, default_user, default_password, sources=sources, topic=topic, **kwargs)



class ExternalJSON(Agent):
    """Gathers and publishes JSON data available via a web api.
    """
    def __init__(self, interval, default_user, default_password, sources=[], topic=PUBLISH_TOPIC, **kwargs):
        super(ExternalJSON, self).__init__(**kwargs)
        self.interval = interval
        self.default_user = default_user
        self.default_password = default_password
        self.sources = sources
        self.topic = topic

        self._validate_sources()

    def _validate_sources(self):
        # Simple validation of sources
        new_sources = []
        for source in self.sources:
            url = source.get("url")
            key_column = source.get("key")
            source_topic = source.get("topic", "")

            if url is None:
                _log.error("Missing url from source!")
                continue

            if key_column is None:
                topic = self.topic(source=source_topic, key="")
                if not topic:
                    _log.error("{url} configured to publish without topic. Removing source".format(url=url))
                    continue

            new_sources.append(source)

        self.sources = new_sources

    @Core.receiver('onstart')
    def onstart(self,sender, **kwargs):
        self.core.periodic(self.interval,self.publish_data)

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
            keys = source.get("key", [])
            source_topic = source.get("topic", "")
            user = source.get("user", self.default_user)
            password = source.get("password", self.default_password)
            path = source.get("path", [])

            if isinstance(path, str):
                path = [path]

            if isinstance(keys, str):
                keys = [keys]

            kwargs = {"params":params}

            if user is not None:
                kwargs["auth"] = HTTPBasicAuth(user, password)

            try:
                r = requests.get(url, **kwargs)
                r.raise_for_status()
                data = r.json()
            except (requests.exceptions.HTTPError, ValueError) as e:
                _log.error("Failure to read from source {url} {reason}".format(url=url, reason=str(e)))
                continue

            try:
                for path_name in path:
                    data = data[path_name]
            except (KeyError, IndexError) as e:
                _log.error("Failure to read from source {url} {reason}".format(url=url, reason=str(e)))
                continue

            if isinstance(data, list) and keys:
                dropped_rows = False
                for row in data:
                    missing_key = False
                    key_value = row

                    try:
                        for key_name in keys:
                            key_value = key_value[key_name]
                    except (KeyError, IndexError, TypeError) as e:
                        missing_key = dropped_rows = True

                    if missing_key:
                        continue

                    if not isinstance(key_value, (str, unicode)) or not key_value:
                        dropped_rows = True
                        continue

                    topic = self.topic(source=source_topic, key=key_value)

                    if not topic:
                        dropped_rows = True
                        continue

                    self.vip.pubsub.publish(peer='pubsub', topic=topic, message=row, headers=headers).get(
                        timeout=10.0)
                if dropped_rows:
                    _log.error("At least one key missing from the data from source {url}".format(url=url))

            else:
                # The topic has already been verified as legit by now.
                topic = self.topic(source=source_topic, key="")
                self.vip.pubsub.publish(peer='pubsub', topic=topic, message=data, headers=headers).get(timeout=10.0)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(json_agent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ =='__main__':
    # Entry point for script
    sys.exit(main())

# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

import logging
import sys
import csv
import requests
from ast import literal_eval
from io import StringIO
from requests.auth import HTTPBasicAuth

from volttron.platform.vip.agent import Agent
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.scheduling import periodic
from volttron.platform.messaging.utils import Topic

utils.setup_logging()
__author__ = 'Kyle Monson'
__copyright__ = 'Copyright (c) 2017, Battelle Memorial Institute'
__license__ = 'Apache 2.0'

_log = logging.getLogger(__name__)
__version__ = '1.0'


PUBLISH_TOPIC = Topic("{base}//{source}//{key}")


def external_data_agent(config_path, **kwargs):
    config = utils.load_config(config_path)

    interval = config.get('interval', 300)
    default_user = config.get('default_user')
    default_password = config.get('default_password')
    global_topic_prefix = config.get('global_topic_prefix', "")
    sources = config.get("sources", [])

    return ExternalData(interval, default_user, default_password, sources, global_topic_prefix, **kwargs)


class ExternalData(Agent):
    """Gathers and publishes JSON data available via a web api.
    """
    def __init__(self, interval, default_user, default_password, sources, global_topic_prefix, **kwargs):
        super(ExternalData, self).__init__(**kwargs)
        self.interval = interval
        self.default_user = default_user
        self.default_password = default_password

        self.periodic = None

        self.default_config = {"interval": interval,
                               "global_topic_prefix": global_topic_prefix,
                               "default_user": default_user,
                               "default_password": default_password}

        self.default_config["sources"] = self.sources = self._validate_sources(sources, global_topic_prefix)

        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")

    def _validate_sources(self, old_sources, global_topic_prefix):
        # Simple validation of sources
        topic = PUBLISH_TOPIC(base=global_topic_prefix, source=None, key=None)
        new_sources = []
        for source in old_sources:
            url = source.get("url")
            key_column = source.get("key")
            source_topic = source.get("topic", "")

            if url is None:
                _log.error("Missing url from source!")
                continue

            if key_column is None:
                topic_str = topic(source=source_topic, key="")
                if not topic_str:
                    _log.error("{url} configured to publish without topic. Removing source".format(url=url))
                    continue

            new_sources.append(source)

        return new_sources

    def _configure(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)

        _log.debug("Configuring External Data agent")

        global_topic_prefix = config.get('global_topic_prefix', "")

        self.sources = self._validate_sources(config.get("sources", []), global_topic_prefix)

        self.topic = PUBLISH_TOPIC(base=global_topic_prefix, source=None, key=None)

        self.default_user = config.get('default_user')
        self.default_password = config.get('default_password')

        try:
            interval = float(config.get("interval", 300.0))
        except ValueError:
            _log.error("Error setting scrape interval, reverting to default of 300 seconds")
            interval = 300.0

        if self.periodic is not None:
            self.periodic.cancel()

        self.periodic = self.core.schedule(periodic(interval), self._publish_data)

    def _publish_data(self):
        for source in self.sources:
            now = utils.get_aware_utc_now()
            now = utils.format_timestamp(now)
            headers = {
                headers_mod.DATE: now,
                headers_mod.TIMESTAMP: now
            }

            url = source.get("url")
            params = source.get("params")
            source_topic = source.get("topic", "")
            user = source.get("user", self.default_user)
            password = source.get("password", self.default_password)
            source_type = source.get("type", "raw")

            kwargs = {"params": params}

            if user is not None:
                kwargs["auth"] = HTTPBasicAuth(user, password)

            try:
                r = requests.get(url, **kwargs)
                r.raise_for_status()
            except Exception as e:
                _log.error("Failure to read from source {url} {reason}".format(url=url, reason=str(e)))
                continue

            try:
                if source_type.lower() == "json":
                    self._handle_json(headers, r, url, source_topic, source)
                elif source_type.lower() == "csv":
                    self._handle_csv(headers, r, url, source_topic, source)
                elif source_type.lower() == "raw":
                    self._handle_raw(headers, r, url, source_topic, source)
            except Exception as e:
                _log.error("General failure during processing of source {url} {reason}".format(url=url, reason=str(e)))

    def _handle_json(self, headers, request, url, source_topic, source_params):
        keys = source_params.get("key", [])
        path = source_params.get("path", [])

        if isinstance(path, str):
            path = [path]

        if isinstance(keys, str):
            keys = [keys]

        try:
            data = request.json()
        except ValueError as e:
            _log.error("Failure to read from source {url} {reason}".format(url=url, reason=str(e)))
            return

        try:
            for path_name in path:
                data = data[path_name]
        except (KeyError, IndexError, TypeError) as e:
            _log.error("Failure to read from source {url} {reason}".format(url=url, reason=str(e)))
            return

        if isinstance(data, list) and keys:
            dropped_rows = False
            for row in data:
                missing_key = False
                key_value = row

                try:
                    for key_name in keys:
                        key_value = key_value[key_name]
                except (KeyError, IndexError, TypeError):
                    missing_key = dropped_rows = True

                if missing_key:
                    continue

                if not isinstance(key_value, str) or not key_value:
                    dropped_rows = True
                    continue

                topic = self.topic(source=source_topic, key=key_value)

                if not topic:
                    dropped_rows = True
                    continue

                self.vip.pubsub.publish(peer='pubsub', topic=topic, message=row, headers=headers).get(timeout=10.0)
            if dropped_rows:
                _log.error("At least one key missing from the data from source {url}".format(url=url))

        else:
            # The topic has already been verified as legit by now.
            topic = self.topic(source=source_topic, key="")
            self.vip.pubsub.publish(peer='pubsub', topic=topic, message=data, headers=headers).get(timeout=10.0)

    def _handle_csv(self, headers, request, url, source_topic, source_params):
        key_column = source_params.get("key", "")
        flatten = source_params.get("flatten", False)
        parse_columns = source_params.get("parse", [])

        file_obj = StringIO(request.content)

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
            csv_data = csv.DictReader(file_obj)

        if parse_columns:
            new_csv_data = []
            for row in csv_data:
                for parse_column in parse_columns:
                    value_string = ""
                    try:
                        value_string = row[parse_column]
                        value = literal_eval(value_string)
                        row[parse_column] = value
                    except KeyError:
                        pass
                    except Exception:
                        if value_string == "":
                            row[parse_column] = None
                new_csv_data.append(row)

            csv_data = new_csv_data

        if key_column:
            dropped_rows = False
            for row in csv_data:
                key = row.pop(key_column, "")
                topic = self.topic(source=source_topic, key=key)
                if topic:
                    self.vip.pubsub.publish(peer='pubsub', topic=topic, message=row, headers=headers).get(timeout=10.0)
                else:
                    dropped_rows = True
            if dropped_rows:
                _log.warning("Skipped rows with invalid topic from {url}".format(url=url))

        else:
            # The topic has already been verified as legit by now.
            topic = self.topic(source=source_topic, key="")
            if flatten:
                data = csv_data[0]
            else:
                data = csv_data
            self.vip.pubsub.publish(peer='pubsub', topic=topic, message=data, headers=headers).get(timeout=10.0)

    def _handle_raw(self, headers, request, url, source_topic, source_params):
        topic = self.topic(source=source_topic, key="")
        self.vip.pubsub.publish(peer='pubsub', topic=topic, message=request.content, headers=headers).get(timeout=10.0)


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(external_data_agent)
    except Exception as e:
        _log.exception('unhandled exception: {}'.format(e))


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())

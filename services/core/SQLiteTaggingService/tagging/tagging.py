# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD Project.
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

# }}}
from __future__ import absolute_import, print_function

import csv
import logging
import sys
import sqlite3
from pkg_resources import resource_string

from volttron.platform.agent import utils
from volttron.platform.agent.base_tagging import BaseTaggingService
from volttron.utils.docs import doc_inherit

from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_GOOD, Status)
__version__ = "1.0"

utils.setup_logging()
_log = logging.getLogger(__name__)

TAGGING_SERVICE_SETUP_FAILED = 'TAGGING_SERVICE_SETUP_FAILED'

def tagging_service(config_path, **kwargs):
    """
    This method is called by the :py:func:`service.tagging.main` to
    parse the passed config file or configuration dictionary object, validate
    the configuration entries, and create an instance of SQLTaggingService

    :param config_path: could be a path to a configuration file or can be a
                        dictionary object
    :param kwargs: additional keyword arguments if any
    :return: an instance of :py:class:`service.tagging.SQLTaggingService`
    """
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)

    database = config_dict['connection']['params']['database']

    assert database is not None

    SQLTaggingService.__name__ = 'SQLTaggingService'
    # TODO replace with utils.update_kwargs_with_config
    kwargs.update(config_dict)
    return SQLTaggingService(**kwargs)


class SQLTaggingService(BaseTaggingService):
    """This is a tagging service agent that writes data to a SQLite database.
    """
    def __init__(self, connection, table_prefix=None, **kwargs):
        """Initialise the tagging service.

        :param connection: dictionary object containing the database 
        connection details
        :param table_prefix: optional prefix to be used for all tag tables
        :param kwargs: additional keyword arguments. (optional identity and
                       topic_replace_list used by parent classes)
        """

        self.connection = connection
        self.tags_table = "tags"
        #self.units_table = "units"  #in version 2
        self.categories_table = "categories"
        self.topic_tags_table = "topic_tags"
        if table_prefix:
            self.tags_table = table_prefix + "_" + self.tags_table
            self.categories_table = table_prefix + "_" + self.categories_table
            self.topic_tags_table = table_prefix + "_" + self.topic_tags_table

        super(SQLTaggingService, self).__init__(**kwargs)

    @doc_inherit
    def setup(self):
        _log.debug("Setup of sqlite tagging agent")
        table_name = ""
        try:
            con = sqlite3.connect(
                self.connection['params']['database'],
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

            cursor = con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='{}' OR "
                "name='{}' OR name='{}';".format(self.tags_table,
                                                 self.categories_table,
                                                 self.topic_tags_table))
            table_names = cursor.fetchall()
            _log.debug(table_names)

            table_name = self.tags_table
            if self.tags_table in table_names:
                _log.info("{} table exists. Assuming initial values have been "
                          "loaded".format(table_name))
            else:
                self.init_tags(con)

            table_name = self.topic_tags_table
            if self.topic_tags_table in table_names:
                _log.info("{} table exists. Assuming initial values "
                          "have been loaded".format(table_name))
            else:
                self.init_topic_tags(con)

            table_name = self.categories_table
            if self.categories_table in table_names:
                _log.info("{} table exists. Assuming initial values "
                          "have been loaded".format(table_name))
            else:
                self.init_categories(con)

            con.close()
        except Exception as e:
            if table_name:
                message = "Initialization of" + table_name +\
                          " table failed with exception: {}" \
                          "Stopping tagging service agent. "
            else:
                message = "Unable to query list of existing tables from the " \
                          "database. Exception: {}. " \
                          "Stopping tagging service agent"

            _log.error(message.format(e.args))
            self.vip.health.set_status(STATUS_BAD,
                                       "Initialization of tag tables failed")
            status = Status.from_json(self.vip.health.get_status_json())
            # status.context = status.context + \
            #                  " Exception: {}".format(e.args) + \
            #                  " Stopping tagging service agent"
            # _log.debug("status:{}".format(status))
            self.vip.health.send_alert(TAGGING_SERVICE_SETUP_FAILED, status)
            self.core.stop()

    def init_tags(self, con):
        con.execute("CREATE TABLE {} "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT  NOT NULL, "
                    "name VARCHAR NOT NULL UNIQUE, "
                    "kind VARCHAR NOT NULL, "
                    "description VARCHAR)".format(self.tags_table))

        _log.debug(self.resource_sub_dir+'/tags.csv')
        csv_str = resource_string(__name__, self.resource_sub_dir+'/tags.csv')
        # csv.DictReader uses first line in file for column headings
        # by default
        dr = csv.DictReader(csv_str.splitlines())  # comma is default delimiter
        to_db = [(i['Name'], i['Kind'], i['Description']) for i in dr]

        cursor = con.cursor()
        cursor.executemany("INSERT INTO {} (name, kind, description) "
                           "VALUES (?, ?, ?);".format(self.tags_table), to_db)
        con.commit()

    def init_categories(self, con):
        con.execute("CREATE TABLE {} "
                    "(name VARCHAR PRIMARY KEY NOT NULL,"
                    "description VARCHAR)".format(self.categories_table))
        _log.debug("created categories table")
        csv_str = resource_string(__name__,
                                  self.resource_sub_dir+'/categories.csv')
        dr = csv.DictReader(csv_str.splitlines())
        to_db = [(i['Name'], i['Description']) for i in dr]
        cursor = con.cursor()
        cursor.executemany("INSERT INTO {} (name, description) "
                           "VALUES (?, ?);".format(self.categories_table), to_db)
        con.commit()

    def init_topic_tags(self, con):
        con.execute(
            "CREATE TABLE {} (topic_prefix TEXT NOT NULL, "
            "tag VARCHAR NOT NULL, value TEXT)".format(self.topic_tags_table))
        con.commit()

    def query_categories(self, skip=0, count=None, order=None):
        con = sqlite3.connect(self.connection['params']['database'],
                              detect_types=sqlite3.PARSE_DECLTYPES |
                                           sqlite3.PARSE_COLNAMES)

        query = '''SELECT name, description FROM ''' + self.categories_table + '''
                   {order_by}
                   {limit}
                   {offset}'''
        order_by = 'ORDER BY name ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY name DESC'
        args = []

        # can't have an offset without a limit
        # -1 = no limit and allows the user to
        # provide just an offset
        if count is None:
            count = -1

        limit_statement = 'LIMIT ?'
        args.append(count)

        offset_statement = ''
        if skip > 0:
            offset_statement = 'OFFSET ?'
            args.append(skip)

        real_query = query.format(limit=limit_statement,
                                  offset=offset_statement,
                                  order_by=order_by)
        _log.debug("Real Query: "  + real_query)
        _log.debug(args)
        cursor = con.execute(real_query, args)
        result = {}
        for row in cursor:
            result[row[0]] = row[1]
        _log.debug(result)
        con.close()
        return result


    def query_tags_by_category(self, category_name, skip=0, count=None, order=None):
        pass



    def query_tags_by_topic(self, topic_prefix, skip=0, count=None,
                            order=None):
        pass

    def insert_tags(self, tags, update_version=False):
        pass

    def insert_topic_tags(self, topic_prefix, tags, update_version=False):
        pass

    def query_topics_by_tags(self, and_condition=None, or_condition=None,
                             regex_and=None, regex_or=None, condition=None):
        pass

def main(argv=sys.argv):
    """ Main entry point for the agent.

    :param argv:
    :return:
    """

    try:
        utils.vip_main(tagging_service, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

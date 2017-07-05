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

import gevent
import re
from pkg_resources import resource_string, resource_exists
from collections import OrderedDict

from volttron.platform.agent import utils
from volttron.platform.agent.base_tagging import BaseTaggingService
from volttron.platform.dbutils.sqlitefuncts import SqlLiteFuncts
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

    SQLiteTaggingService.__name__ = 'SQLiteTaggingService'
    utils.update_kwargs_with_config(kwargs,config_dict)
    return SQLiteTaggingService(**kwargs)


class SQLiteTaggingService(BaseTaggingService):
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
        self.category_tags_table = "category_tags"
        if table_prefix:
            self.tags_table = table_prefix + "_" + self.tags_table
            self.categories_table = table_prefix + "_" + self.categories_table
            self.topic_tags_table = table_prefix + "_" + self.topic_tags_table
            self.category_tags_table = table_prefix + "_" + \
                                       self.category_tags_table
        self.sqlite_utils = SqlLiteFuncts(self.connection['params'], None)
        super(SQLiteTaggingService, self).__init__(**kwargs)

    @doc_inherit
    def setup(self):
        _log.debug("Setup of sqlite tagging agent")
        err_message = ""
        if not resource_exists(__name__, self.resource_sub_dir):
            err_message = "Unable to load resources directory. No such " \
                          "directory:{}. Please make sure that setup.py has " \
                          "been updated to include the resources directory. " \
                          "If the name of the resources directory is " \
                          "anything other than \"resources\" please configure " \
                          "it in the agent's configuration file using the " \
                          "key \"resources_sub_directory\" Init of tagging " \
                          "service failed. Stopping tagging service " \
                          "agent".format(self.resource_sub_dir)

        table_names = []
        try:
            stmt = "SELECT name FROM sqlite_master " \
                "WHERE type='table' AND name='{}' OR " \
                "name='{}' OR name='{}';".format(self.tags_table,
                                                 self.categories_table,
                                                 self.category_tags_table,
                                                 self.topic_tags_table)
            table_names = self.sqlite_utils.select(stmt, None, fetch_all=True)
            _log.debug(table_names)
        except Exception as e:
            err_message = "Unable to query list of existing tables from the " \
                          "database. Exception: {}. Stopping tagging " \
                          "service agent".format(e.args)
        table_name = ""
        try:
            table_name = self.tags_table
            if self.tags_table in table_names:
                _log.info("{} table exists. Assuming initial values have been "
                          "loaded".format(table_name))
            else:
                self.init_tags()

            table_name = self.topic_tags_table
            if self.topic_tags_table in table_names:
                _log.info("{} table exists. Assuming initial values "
                          "have been loaded".format(table_name))
            else:
                self.init_topic_tags()

            table_name = self.categories_table
            if self.categories_table in table_names:
                _log.info("{} table exists. Assuming initial values "
                          "have been loaded".format(table_name))
            else:
                self.init_categories()

            table_name = self.category_tags_table
            if self.category_tags_table in table_names:
                _log.info("{} table exists. Assuming initial values "
                          "have been loaded".format(table_name))
            else:
                self.init_category_tags()

        except Exception as e:
            err_message = "Initialization of " + table_name + \
                          " table failed with exception: {}" \
                          "Stopping tagging service agent. ".format(e.args)
        if err_message:
            _log.error(err_message)
            self.vip.health.set_status(STATUS_BAD,
                                       "Initialization of tagging service "
                                       "failed")
            status = Status.from_json(self.vip.health.get_status_json())
            # status.context = status.context + \
            #                  " Exception: {}".format(e.args) + \
            #                  " Stopping tagging service agent"
            # _log.debug("status:{}".format(status))
            self.vip.health.send_alert(TAGGING_SERVICE_SETUP_FAILED, status)
            self.core.stop()

    def load_valid_tags(self):
        # Now cache list of tags and kind/type for validation during insert
        cursor = self.sqlite_utils.select(
            "SELECT name, kind from " + self.tags_table, fetch_all=False)
        for record in cursor:
            self.valid_tags[record[0]] = record[1]

    def init_tags(self):
        file_name = self.resource_sub_dir + '/tags.csv'
        _log.debug("Loading file :" + file_name)
        self.sqlite_utils.execute_stmt("CREATE TABLE {}"
                    "(name VARCHAR PRIMARY KEY, "
                    "kind VARCHAR NOT NULL, "
                    "description VARCHAR)".format(
                        self.tags_table))

        _log.debug(self.resource_sub_dir+'/tags.csv')
        csv_str = resource_string(__name__, file_name)
        # csv.DictReader uses first line in file for column headings
        # by default
        dr = csv.DictReader(csv_str.splitlines())  # comma is default delimiter
        to_db = [(i['name'], i['kind'], i['description'].decode('utf8')) for i in dr]
        self.sqlite_utils.execute_many(
            "INSERT INTO {} (name, kind, description) "
            "VALUES (?, ?, ?);".format(self.tags_table),
            to_db)
        self.sqlite_utils.commit()

    def init_categories(self):
        file_name = self.resource_sub_dir + '/categories.csv'
        _log.debug("Loading file :" + file_name)
        self.sqlite_utils.execute_stmt("CREATE TABLE {}"
                    "(name VARCHAR PRIMARY KEY NOT NULL,"
                    "description VARCHAR)".format(self.categories_table))
        _log.debug("created categories table")
        csv_str = resource_string(__name__, file_name)
        dr = csv.DictReader(csv_str.splitlines())
        to_db = [(i['name'], i['description'].decode('utf8')) for i in dr]
        _log.debug("Categories in: {}".format(to_db))
        self.sqlite_utils.execute_many(
            "INSERT INTO {} (name, description) "
                "VALUES (?, ?);".format(self.categories_table),
            to_db)
        self.sqlite_utils.commit()

    def init_category_tags(self):
        file_name = self.resource_sub_dir + '/category_tags.txt'
        _log.debug("Loading file :" + file_name)
        self.sqlite_utils.execute_stmt("CREATE TABLE {} "
                    "(category VARCHAR NOT NULL,"
                    "tag VARCHAR NOT NULL,"
                    "PRIMARY KEY (category, tag))".format(
                        self.category_tags_table))
        _log.debug("created {} table".format(self.category_tags_table))
        csv_str = resource_string(__name__, file_name)
        to_db = []
        if csv_str:
            current_category = ""
            tags = set()
            for line in csv_str.splitlines():
                if not line or line.startswith("##"):
                    continue
                if line.startswith("#") and line.endswith("#"):
                    new_category = line.strip()[1:-1]
                    if len(tags) > 0:
                        to_db.extend([(current_category,x) for x in tags])
                    current_category = new_category
                    tags = set()
                else:
                    temp= line.split(":") #ignore description
                    tags.update(re.split(" +", temp[0]))

            # insert last category after loop
            if len(tags)>0:
                to_db.extend([(current_category, x) for x in tags])
            self.sqlite_utils.execute_many(
                "INSERT INTO {} (category, tag) "
                "VALUES (?, ?);".format(self.category_tags_table), to_db)
            self.sqlite_utils.commit()
        else:
            _log.warn("No category to tags mapping to initialize. No such "
                      "file " + file_name)

    def init_topic_tags(self):
        self.sqlite_utils.execute_stmt(
            "CREATE TABLE {} (topic_prefix TEXT NOT NULL, "
            "tag VARCHAR NOT "
            "NULL, value TEXT,"
            "PRIMARY KEY (topic_prefix, tag))".format(
                self.topic_tags_table, self.tags_table))
        self.sqlite_utils.execute_stmt(
            "CREATE INDEX IF NOT EXISTS idx_tag ON " +
            self.topic_tags_table + "(tag ASC);")
        self.sqlite_utils.commit()

    def query_categories(self, include_description=False, skip=0, count=None,
                       order="FIRST_TO_LAST"):

        query = '''SELECT name, description FROM ''' \
                + self.categories_table + '''
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
        _log.debug("Real Query: " + real_query)
        _log.debug(args)
        cursor = self.sqlite_utils.select(real_query, args, fetch_all=False)
        result = OrderedDict()
        for row in cursor:
            _log.debug(row[0])
            result[row[0]] = row[1]
        _log.debug(result.keys())
        _log.debug(result.values())
        cursor.close()
        if include_description:
            return result.items()
        else:
            return result.keys()

    def query_tags_by_category(self, category, include_kind=False,
                               include_description=False, skip=0, count=None,
                               order="FIRST_TO_LAST"):
        query = 'SELECT name, kind, description FROM {tag} as t, ' \
                '{category_tag} as c ' \
                'WHERE ' \
                't.name = c.tag AND c.category = "{category}" ' \
                '{order_by} ' \
                '{limit} ' \
                '{offset}'
        order_by = 'ORDER BY name ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY name DESC'
        args = []

        _log.debug("After orderby. skip={}".format(skip))
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
        _log.debug("before real querye")
        real_query = query.format(
            tag=self.tags_table,
            category_tag=self.category_tags_table,
            category=category,
            limit=limit_statement,
            offset=offset_statement,
            order_by=order_by)
        _log.debug("Real Query: " + real_query)
        _log.debug(args)
        cursor = None
        try:
            cursor = self.sqlite_utils.select(real_query, args,
                                              fetch_all=False)
            result = []
            for row in cursor:
                _log.debug(row[0])
                record = [row[0]]
                if include_kind:
                    record.append(row[1])
                if include_description:
                    record.append(row[2])
                if include_description or include_kind:
                    result.append(record)
                else:
                    result.append(row[0])
            return result
        finally:
            if cursor:
                cursor.close()

    def query_tags_by_topic(self, topic_prefix, include_kind=False,
                            include_description=False, skip=0, count=None,
                            order="FIRST_TO_LAST"):

        query = 'SELECT name, value, kind, description FROM {tags} as t1, ' \
                '{topic_tags} as t2 ' \
                'WHERE ' \
                't1.name = t2.tag ' \
                'AND t2.topic_prefix = "{topic_prefix}" ' \
                '{order_by} ' \
                '{limit} ' \
                '{offset}'
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
        _log.debug("before real query")
        real_query = query.format(
            tags=self.tags_table, topic_tags=self.topic_tags_table,
            topic_prefix=topic_prefix, limit=limit_statement,
            offset=offset_statement, order_by=order_by)
        _log.debug("Real Query: " + real_query)
        _log.debug(args)
        cursor = None
        try:
            cursor = self.sqlite_utils.select(real_query, args,
                                              fetch_all=False)
            result = []
            for row in cursor:
                _log.debug(row[0])
                record = [row[0], row[1]]
                if include_kind:
                    record.append(row[2])
                if include_description:
                    record.append(row[3])
                result.append(record)

            return result
        finally:
            if cursor:
                cursor.close()

    def insert_topic_tags(self, tags, update_version=False):
        t = dict()
        to_db =[]
        for topic_name, topic_tags in tags.iteritems():
            for tag_name, tag_value in topic_tags.iteritems():
                if not self.valid_tags.has_key(tag_name):
                    raise ValueError("Invalid tag name:{}".format(tag_name))
                if tag_name == 'id':
                    _log.warn("id tags are not explicitly stored. "
                              "topic_prefix servers as unique identifier for"
                              "an entity. id value sent({}) will not be "
                              "stored".format(tag_value))
                    continue
                # TODO: Validate and convert values based on tag kind/type
                # for example, for Marker tags set value as true even if
                # value passed is None.
                #tag_value = get_tag_value(tag_value,
                #                          self.valid_tags[tag_name])

                to_db.append((topic_name, tag_name, tag_value))

        self.sqlite_utils.execute_many(
            "REPLACE INTO {} (topic_prefix, tag, value) "
                "VALUES (?, ?, ?);".format(self.topic_tags_table),
            to_db)
        self.sqlite_utils.commit()

    def query_topics_by_tags(self, and_condition=None, or_condition=None,
                             regex_and=None, regex_or=None, condition=None,
                             skip=0, count=None, order=None):
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

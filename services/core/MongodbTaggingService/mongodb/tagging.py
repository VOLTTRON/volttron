# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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
from __future__ import absolute_import, print_function

import collections
import csv
import logging
import sys
from collections import OrderedDict

import pymongo
import re
from pkg_resources import resource_string, resource_exists
from pymongo.errors import BulkWriteError

from volttron.platform.agent import utils
from volttron.platform.agent.base_tagging import BaseTaggingService
from volttron.platform.dbutils import mongoutils
from volttron.platform.messaging.health import (STATUS_BAD, Status)
from volttron.utils.docs import doc_inherit

__version__ = "1.1"

utils.setup_logging()
_log = logging.getLogger(__name__)
TAGGING_SERVICE_SETUP_FAILED = 'TAGGING_SERVICE_SETUP_FAILED'


def tagging_service(config_path, **kwargs):
    """
    This method is called by the :py:func:`service.tagging.main` to
    parse the passed config file or configuration dictionary object, validate
    the configuration entries, and create an instance of MongodbTaggingService

    :param config_path: could be a path to a configuration file or can be a
     dictionary object
    :param kwargs: additional keyword arguments if any
    :return: an instance of :py:class:`service.tagging.SQLTaggingService`
    """
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)

    if not config_dict.get('connection') or \
            not config_dict.get('connection').get('params') or \
            not config_dict.get('connection').get('params').get('database'):
        raise ValueError("Missing database connection parameters. Agent "
                         "configuration should contain database connection "
                         "parameters with the details about type of database"
                         "and name of database. Please refer to sample "
                         "configuration file in Agent's source directory.")

    utils.update_kwargs_with_config(kwargs, config_dict)
    return MongodbTaggingService(**kwargs)


class MongodbTaggingService(BaseTaggingService):
    """This is a tagging service agent that writes data to a Mongo database.
    For instance with large amount of tags and frequent tag queries, a NOSQL 
    database such as Mongodb would provide better efficiency than SQLite. 
    """
    def __init__(self, connection, table_prefix=None, **kwargs):
        """Initialise the tagging service.

        :param connection: dictionary object containing the database 
         connection details
        :param table_prefix: optional prefix to be used for all tag tables
        :param kwargs: additional keyword arguments. (optional identity and
         topic_replace_list used by parent classes)
        """

        super(MongodbTaggingService, self).__init__(**kwargs)
        self.connection = connection
        self._client = mongoutils.get_mongo_client(connection['params'])
        self.tags_collection = "tags"
        self.tag_refs_collection = "tag_refs"
        #self.units_table = "units"  #in version 2
        self.categories_collection = "categories"
        self.topic_tags_collection = "topic_tags"
        if table_prefix:
            self.tags_collection = table_prefix + "_" + \
                                   self.tags_collection
            self.tag_refs_collection = table_prefix + "_" + \
                                       self.tag_refs_collection
            self.categories_collection = table_prefix + "_" + \
                                         self.categories_collection
            self.topic_tags_collection = table_prefix + "_" + \
                                         self.topic_tags_collection

    @doc_inherit
    def setup(self):
        """
        Read resource files and load list of valid tags, categories,
        tags grouped by categories, list of reference tags and its parent.
        :return:
        """
        _log.debug("Setup of mongodb tagging agent")
        err_message = ""
        collections = []
        db = None
        try:
            db = self._client.get_default_database()
            collections = db.collection_names(include_system_collections=False)
            _log.debug(collections)
        except Exception as e:
            err_message = "Unable to query list of existing tables from the " \
                          "database. Exception in init of tagging service: {}. " \
                          "Stopping tagging service agent".format(e.args)
        collection = ""
        try:
            collection = self.tags_collection
            if self.tags_collection in collections:
                _log.info("{} collection exists. Assuming initial values have "
                          "been loaded".format(collection))
            else:
                self._init_tags(db)
                self._init_category_tags(db)

            collection = self.tag_refs_collection
            if self.tag_refs_collection in collections:
                _log.info("{} collection exists. Assuming initial values have "
                          "been loaded".format(collection))
            else:
                self._init_tag_refs(db)

            collection = self.categories_collection
            if self.categories_collection in collections:
                _log.info("{} collection exists. Assuming initial values "
                          "have been loaded".format(collection))
            else:
                self._init_categories(db)

        except Exception as e:
            err_message = "Initialization of " + collection + \
                          " collection failed with exception: {}" \
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

    @doc_inherit
    def load_valid_tags(self):
        # Now cache list of tags and kind/type for validation during
        # insert
        db = self._client.get_default_database()
        cursor = db[self.tags_collection].find({}, projection=['_id', 'kind'])
        for record in cursor:
            self.valid_tags[record['_id']] = record['kind']

    @doc_inherit
    def load_tag_refs(self):
        # Now cache ref tags and its parent
        db = self._client.get_default_database()
        cursor = db[self.tag_refs_collection].find({}, projection=['_id',
                                                                   'parent'])
        for record in cursor:
            self.tag_refs[record['_id']] = record['parent']
        _log.debug("After load tag_refs is {}".format(self.tag_refs))

    def _init_tags(self, db):
        file_path = self.resource_sub_dir+'/tags.csv'
        _log.debug("Loading file :" + file_path)
        with open(file_path, 'r') as content_file:
            csv_str = content_file.read()
        if csv_str:
            # csv.DictReader uses first line in file for column headings
            # by default
            dr = csv.DictReader(csv_str.splitlines())
            bulk_tags = db[self.tags_collection].initialize_ordered_bulk_op()
            for i in dr:
                bulk_tags.insert({"_id":i['name'],
                                  "kind":i['kind'],
                                  "description":i['description']})
            bulk_tags.execute()
        else:
            raise ValueError(
                "Unable to load list of reference tags and its parent. No "
                "such file: {}".format(file_path))

    def _init_tag_refs(self, db):
        file_path = self.resource_sub_dir+'/tag_refs.csv'
        _log.debug("Loading file :" + file_path)
        with open(file_path, 'r') as content_file:
            csv_str = content_file.read()

        if csv_str:
            # csv.DictReader uses first line in file for column headings
            # by default
            dr = csv.DictReader(csv_str.splitlines())
            bulk_tags = db[
                self.tag_refs_collection].initialize_ordered_bulk_op()
            for i in dr:
                bulk_tags.insert({"_id":i['tag'],
                                  "parent":i['parent_tag']})
            bulk_tags.execute()
        else:
            raise ValueError(
                "Unable to load list of reference tags and its parent. No "
                "such file: {}".format(file_path))


    def _init_categories(self, db):
        file_path = self.resource_sub_dir + '/categories.csv'
        _log.debug("Loading file :" + file_path)
        with open(file_path, 'r') as content_file:
            csv_str = content_file.read()
        if csv_str:
            dr = csv.DictReader(csv_str.splitlines())
            bulk = db[
                self.categories_collection].initialize_ordered_bulk_op()
            for i in dr:
                bulk.insert({"_id": i['name'],
                             "description": i['description']})
            bulk.execute()
        else:
            _log.warn("No categories to initialize. No such file "+ file_path)

    def _init_category_tags(self, db):
        file_path = self.resource_sub_dir + '/category_tags.txt'
        _log.debug("Loading file :" + file_path)
        with open(file_path, 'r') as content_file:
            txt_str = content_file.read()

        bulk_tags = db[self.tags_collection].initialize_ordered_bulk_op()
        if txt_str:
            current_category = ""
            tags = set()
            mapping = collections.defaultdict(set)
            for line in txt_str.splitlines():
                if not line or line.startswith("##"):
                    continue
                if line.startswith("#") and line.endswith("#"):
                    new_category = line.strip()[1:-1]
                    if len(tags) > 0:
                        for tag in tags:
                            mapping[tag].add(current_category)
                    current_category = new_category
                    tags = set()
                else:
                    temp= line.split(":")  # ignore description
                    tags.update(re.split(" +", temp[0]))
            if len(tags)>0:
                for tag in tags:
                    mapping[tag].add(current_category)

            for tag in mapping.keys():
                bulk_tags.find({"_id": tag}).update(
                    {'$set': {"categories": list(mapping[tag])}})

            bulk_tags.execute()
            db[self.tags_collection].create_index(
                [('categories', pymongo.ASCENDING)], background=True)

        else:
            _log.warn("No category to tags mapping to initialize. No such "
                      "file " + file_path)

    @doc_inherit
    def query_categories(self, include_description=False, skip=0, count=None,
                         order="FIRST_TO_LAST"):
        db = self._client.get_default_database()
        order_by = pymongo.ASCENDING
        if order == 'LAST_TO_FIRST':
            order_by = pymongo.DESCENDING
        skip_count = 0
        if skip > 0:
            skip_count = skip

        if count is None:
            cursor = db[self.categories_collection].find(
                projection=['_id', 'description'], skip=skip_count,
                sort=[('_id', order_by)])
        else:
            cursor = db[self.categories_collection].find(
                projection=['_id', 'description'], skip=skip_count,
                limit=count, sort=[('_id',order_by)])

        result_dict = list(cursor)
        results = OrderedDict()
        for r in  result_dict:
            results[r['_id']] = r.get('description',"")

        if include_description:
            return results.items()
        else:
            return results.keys()

    @doc_inherit
    def query_tags_by_category(self, category, include_kind=False,
                               include_description=False, skip=0, count=None,
                               order="FIRST_TO_LAST"):
        db = self._client.get_default_database()
        order_by = pymongo.ASCENDING
        if order == 'LAST_TO_FIRST':
            order_by = pymongo.DESCENDING
        skip_count = 0
        if skip > 0:
            skip_count = skip

        _log.debug("category: {}".format(category))

        if count is None:
            cursor = db[self.tags_collection].find(
                {'categories': {'$in': [category]}},
                projection=['_id', 'kind', 'description'], skip=skip_count,
                sort=[('_id', order_by)])
        else:
            cursor = db[self.tags_collection].find(
                {'categories': {'$in': [category]}},
                projection=['_id', 'kind', 'description'], skip=skip_count,
                limit=count, sort=[('_id', order_by)])

        records = list(cursor)
        results = []
        for r in records:
            results_element = [r['_id']]
            if include_kind:
                results_element.append(r['kind'])
            if include_description:
                results_element.append(r['description'])
            if include_kind or include_description:
                results.append(results_element)
            else:
                results.append(r['_id'])
        return results

    @doc_inherit
    def insert_topic_tags(self, tags, update_version=False):
        db = self._client.get_default_database()
        bulk = db[self.topic_tags_collection].initialize_unordered_bulk_op()
        result = dict()
        result['info'] = dict()
        result['error'] = dict()
        execute = False
        for topic_pattern, topic_tags in tags.items():
            for tag_name, tag_value in topic_tags.items():
                if not self.valid_tags.has_key(tag_name):
                    raise ValueError(
                        "Invalid tag name:{}".format(tag_name))
                # TODO: Validate and convert values based on tag kind/type
                # for example, for Marker tags set value as true even if
                # value passed is None.
                # tag_value = get_tag_value(tag_value,
                #                          self.valid_tags[tag_name])
                if tag_name == 'id' and tag_value is not None:
                    _log.warn("id tags are not explicitly stored. "
                              "topic prefix servers as unique identifier for"
                              "an entity. id value sent({}) will not be "
                              "stored".format(tag_value))
            prefixes = self.get_matching_topic_prefixes(topic_pattern)
            if not prefixes:
                result['error'][topic_pattern] = "No matching topic found"
                continue
            result['info'][topic_pattern] = []
            for prefix in prefixes:
                temp = topic_tags.copy()
                temp['_id'] = prefix
                temp['id'] = prefix
                execute = True
                bulk.find({'_id': prefix}).upsert().update_one(
                    {'$set': temp})
                result['info'][topic_pattern].append(prefix)
            if len(result['info'][topic_pattern]) == 1 and \
                topic_pattern == result['info'][topic_pattern][0]:
                # means value sent was actually some pattern so add
                # info to tell user the list of topic prefix that matched
                # the pattern sent
                _log.debug("topic passed is exact name. Not pattern. Removing"
                           " from result info: {}".format(topic_pattern))
                result['info'].pop(topic_pattern)
        if execute:
            try:
                bulk.execute()
            except BulkWriteError as bwe:
                errors = bwe.details['writeErrors']
                _log.error("bwe error count {}".format(len(errors)))
                for e in errors:
                    _log.error(e['op'])
                    result['error'][e['op']['q']['_id']] = e['errmsg']

        return result

    @doc_inherit
    def query_tags_by_topic(self, topic_prefix, include_kind=False,
                            include_description=False, skip=0, count=None,
                            order="FIRST_TO_LAST"):
        db = self._client.get_default_database()
        _log.debug("topic_prefix: {}".format(topic_prefix))
        cursor = db[self.topic_tags_collection].find({"_id": topic_prefix},
                                                     projection={'_id': False})
        l = list(cursor)
        if l and len(l) == 1:
            d = l[0]
        else:
            _log.debug("tags for topic_prefix {} is {}".format(topic_prefix,
                                                               l))
            return []

        reverse = False
        if order == 'LAST_TO_FIRST':
            reverse = True
        ordered_result_dict = OrderedDict(sorted(d.items(), reverse=reverse))
        _log.debug("Ordered tags: {}".format(ordered_result_dict))
        #Now get the kind and description for each of the tag in earlier
        # result dict
        skip_count = 0
        if skip:
            skip_count = skip
        if count is None:
            count = -1
        meta = {}
        if include_description or include_kind:
            cursor = db[self.tags_collection].find(
                {"_id":{"$in":d.keys()}})
            records = list(cursor)
            for r in records:
                meta[r['_id']] = (r['kind'], r['description'])

        results = []
        counter = 0
        for tag, value in ordered_result_dict.items():
            counter = counter + 1
            if counter <= skip:
                continue
            if count < 0 or counter <= (count + skip_count):
                results_element = [tag, value]
                if include_kind:
                    results_element.append(meta[tag][0])
                if include_description:
                    results_element.append(meta[tag][1])
                results.append(results_element)
            elif counter > (count+skip_count):
                break

        return results

    @doc_inherit
    def query_topics_by_tags(self, ast, skip=0, count=None, order=None):

        if count is None:
            count = 100
        skip_count = 0
        if skip > 0:
            skip_count = skip
        order_by = 1
        if order == 'LAST_TO_FIRST':
            order_by = -1
        sub_queries = list()
        find_cond = mongoutils.get_tagging_queries_from_ast(ast,
                                                            self.tag_refs,
                                                            sub_queries)

        _log.debug("main query condition: {}".format(find_cond))
        _log.debug("sub queries: {}".format(sub_queries))
        db = self._client.get_default_database()
        if sub_queries:
            i = 1
            for sub_query in sub_queries:
                cursor = db[self.topic_tags_collection].find(sub_query,
                                                             ['_id'])
                result = [(row['_id']) for row in cursor]
                cursor.close()
                _log.debug("Subquery result is: {}".format(result))
                _log.debug("Calling find replace for "
                           "temp val {}".format("##VOLTTRON_Q" + str(i)))
                self._find_replace(find_cond, "##VOLTTRON_Q" + str(i), result)
                _log.debug("condition after replace : {}".format(find_cond))
                i += 1

        cursor = db[self.topic_tags_collection].find(find_cond, ['_id'])
        cursor = cursor.skip(skip_count).limit(count)
        cursor = cursor.sort([("_id", order_by)])
        topic_prefix = [(row['_id']) for row in cursor]
        cursor.close()
        return topic_prefix

    def _find_replace(self, obj, temp_value, new_value):
        # Utility function used to replace sub query place holders with
        # results of the sub query since mongo does not support nested queries
        _log.debug("In find_replace. obj ={} temp_val={} "
                   "new_val={}".format(obj, temp_value, new_value))
        if not isinstance(obj, dict):
            return
        for k, v in obj.items():
            _log.debug("k={} v={}".format(k, v))
            if isinstance(v, dict):
                _log.debug("Calling with obj {}".format(v))
                found = self._find_replace(v, temp_value, new_value)
                if found:
                    return
            elif isinstance(v, list):
                # and/or/in condition
                for list_item in v:
                    found = self._find_replace(list_item, temp_value,
                                               new_value)
                    if found:
                        return

            else:
                _log.debug("In find_replace. k={} v={} temp_val={} "
                           "new_val={}".format(
                           k, v, temp_value, new_value))
                if v == temp_value:
                    obj[k] = new_value
                    return True


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
